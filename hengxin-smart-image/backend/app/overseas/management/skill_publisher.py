"""Privileged publisher: a single UDS listener, bounded input, no package execution."""
import asyncio
import os
import socket
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from app.db.session import session_factory
from . import skill_publication as publication
from .installed_catalog import root_config
from .skill_transfer_client import SOCKET_DEFAULT, bounded_stream, parse_body
from .skill_transfer_schema import SkillDelete, SkillReclaim, TransferCreate, TransferInstall
from .skill_transfer_store import TransferStore

RECOVERY_INTERVAL = 5


def create_app(store, factory, *, publication=publication, allow_maintenance=True):
    lock = asyncio.Lock()

    @asynccontextmanager
    async def lifespan(app):
        def recover_pending():
            try:
                with factory() as session:
                    publication.recover(store, session)
            except (ValueError, OSError, SQLAlchemyError):
                # The durable journal and 503 catalog remain until the underlying failure is fixed.
                # Retrying a committed deletion requires no browser-local request state.
                return

        stopping = asyncio.Event()
        async def retry():
            while not stopping.is_set():
                try:
                    await asyncio.wait_for(stopping.wait(), timeout=RECOVERY_INTERVAL)
                except TimeoutError:
                    async with lock:
                        recover_pending()

        recover_pending()
        recovery = asyncio.create_task(retry())
        try:
            yield
        finally:
            stopping.set()
            await recovery

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)

    @app.exception_handler(ValueError)
    @app.exception_handler(OSError)
    async def invalid(request, error):
        return JSONResponse({'detail': 'Skill 存储或完整性校验失败，可查询记录后重试'}, status_code=503)

    @app.exception_handler(TimeoutError)
    async def timeout(request, error):
        return JSONResponse({'detail': '文件传输超时，已保留上传记录，请重试该文件'}, status_code=408)

    def actor_id(request):
        try:
            return UUID(request.headers.get('X-Actor-Id', ''))
        except ValueError:
            raise HTTPException(403, '发布请求身份无效') from None

    @app.get('/health')
    def health():
        if (store.installed_root / '.pending.json').exists():
            return JSONResponse({'status': 'awaiting-recovery'}, status_code=503)
        return {'status': 'ok'}

    @app.api_route('/transfers', methods=['GET', 'POST'])
    async def transfers(request: Request):
        actor = actor_id(request)
        body = await parse_body(request, TransferCreate) if request.method == 'POST' else None
        async with lock:
            with factory() as session:
                publication.authorize(session, actor)
                publication.recover(store, session)
                publication.authorize(session, actor)  # Recovery may have committed and released its locks.
                if body:
                    return store.create(body, actor, request.headers.get('Idempotency-Key'))
                result = store.list(actor)
                result['items'] = [publication.transfer_status(store, session, row) for row in result['items']]
                return result

    @app.api_route('/transfers/{transfer_id}', methods=['GET', 'DELETE'])
    async def transfer(transfer_id: UUID, request: Request):
        actor = actor_id(request)
        async with lock:
            with factory() as session:
                publication.authorize(session, actor)
                publication.recover(store, session)
                publication.authorize(session, actor)
                state = publication.transfer_status(store, session, store.load(transfer_id, actor))
                if request.method == 'DELETE':
                    return store.cancel(transfer_id, actor)
                return state

    @app.put('/transfers/{transfer_id}/files')
    async def upload(transfer_id: UUID, request: Request, path: str):
        actor = actor_id(request)
        async with lock:
            with factory() as session:
                publication.authorize(session, actor)
                publication.recover(store, session)
                publication.authorize(session, actor)
                publication.transfer_status(store, session, store.load(transfer_id, actor))
                # Release the permission lock before streaming; installation rechecks authorization.
                session.rollback()
                async with asyncio.timeout(150):
                    return await store.upload(transfer_id, path, bounded_stream(request), actor)

    @app.post('/transfers/{transfer_id}/validate')
    async def validate(transfer_id: UUID, request: Request):
        actor = actor_id(request)
        async with lock:
            with factory() as session:
                publication.authorize(session, actor)
                publication.recover(store, session)
                publication.authorize(session, actor)
                publication.transfer_status(store, session, store.load(transfer_id, actor))
                return store.validate(transfer_id, actor)

    @app.post('/transfers/{transfer_id}/install')
    async def install(transfer_id: UUID, request: Request):
        actor = actor_id(request)
        body = await parse_body(request, TransferInstall)
        async with lock:
            try:
                with factory() as session:
                    publication.authorize(session, actor)
                    publication.recover(store, session)
                    return publication.install(store, session, actor, str(transfer_id), body.baseRelease)
            except (ValueError, OSError, HTTPException) as error:
                if not isinstance(error, HTTPException) or error.status_code not in (403, 404):
                    try:
                        state = store.load(transfer_id, actor)
                        if state['status'] not in ('installed', 'cancelled'):
                            state.update(status='failed', error='安装未完成，请查询状态、重新校验后重试')
                            store.save(state)
                    except (OSError, HTTPException):
                        pass  # Preserve the original failure when the status volume itself is unavailable.
                raise

    @app.delete('/skills/{skill_id}')
    async def delete(skill_id: UUID, request: Request):
        actor = actor_id(request)
        body = await parse_body(request, SkillDelete)
        async with lock:
            with factory() as session:
                publication.authorize(session, actor)
                publication.recover(store, session)
                return publication.delete(store, session, actor, str(skill_id), body)

    @app.post('/maintenance/reclaim')
    async def reclaim(request: Request):
        # This private UDS route has no corresponding public API/proxy route.
        if not allow_maintenance:
            raise HTTPException(404, '操作不可用')
        from .skill_maintenance import reclaim as run
        actor = actor_id(request)
        body = await parse_body(request, SkillReclaim)
        async with lock:
            with factory() as session:
                publication.recover(store, session)
                return run(store, session, actor, body.release, body.dryRun)

    return app


def serve(store, app, path):
    """Run one root-owned publisher on its approved local socket."""
    import fcntl
    import stat
    import uvicorn
    if os.geteuid() != 0:
        raise RuntimeError('Skill publisher must run as root')
    os.umask(0o022)
    # A process-wide advisory lock prevents multiple services publishing simultaneously.
    with (store.path / '.publisher.lock').open('a') as process_lock:
        fcntl.flock(process_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        path = Path(path)
        if not path.is_absolute():
            raise ValueError('Publisher socket must be absolute')
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
        from .installed_tree import safe_directory
        safe_directory(path.parent, protected=True)
        os.chown(path.parent, 0, 10001)
        os.chmod(path.parent, 0o750)
        if path.exists():
            if not stat.S_ISSOCK(path.lstat().st_mode):
                raise ValueError('Refusing to replace a non-socket path')
            path.unlink()
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(str(path))
        os.chown(path, 0, 10001)
        os.chmod(path, 0o660)
        listener.listen(128)
        try:
            server = uvicorn.Server(uvicorn.Config(app,
                access_log=False, log_level='info', timeout_keep_alive=5))
            server.run(sockets=[listener])
        finally:
            listener.close()
            path.unlink(missing_ok=True)


def main():
    if os.geteuid() != 0:
        raise RuntimeError('Skill publisher must run as root')
    os.umask(0o022)
    root, protected = root_config()
    store = TransferStore(os.environ.get('HX_SKILL_TRANSFER_ROOT',
                          '/var/lib/hengxin-overseas/skill-transfers'), root, protected)
    serve(store, create_app(store, session_factory()), os.environ.get('HX_SKILL_PUBLISH_SOCKET', SOCKET_DEFAULT))


if __name__ == '__main__':
    main()
