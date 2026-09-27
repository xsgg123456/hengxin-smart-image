"""Real auth + route dependencies, isolated SQL pool, and controlled object I/O."""
import asyncio
import hashlib
import json
from dataclasses import FrozenInstanceError
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4
from zipfile import ZipFile

import pytest
from fastapi import FastAPI
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.db import session as db
from app.errors import register_errors
from app.models import Base
from app.modules.auth.sessions import issue_session
from app.modules.files import router, downloads
from app.modules.files.delivery import FileDelivery
from app.modules.api_image_edits import router as api_router
from app.modules.api_image_edits.models import ApiFile, ApiTask, ApiItem, ApiChannel
from app.resource_models import FileRecord, UserRecord
from app.storage.minio_store import get_store


@pytest.fixture
def media_env(tmp_path, monkeypatch):
    engine = create_engine(f'sqlite:///{tmp_path / "media.db"}',
                           connect_args={'check_same_thread': False}, pool_size=1, max_overflow=0)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    uid, fid, aid, tid = [uuid4() for _ in range(4)]
    data = b'original image bytes'
    with factory.begin() as session:
        session.add(UserRecord(id=uid, name='reader', role='operator', status='active',
                               identity_source='wecom'))
        for model, key in [(FileRecord, fid), (ApiFile, aid)]:
            session.add(model(id=key, owner_id=uid, name='原图.png', bucket='private',
                              object_key=str(key), content_type='image/png', size_bytes=len(data),
                              checksum=hashlib.sha256(data).hexdigest(), width=8, height=6,
                              status='ready'))
        session.add(ApiTask(id=tid, owner_id=uid, operator_id=uid, name='set', prompt='test',
                            material_id=aid, parameters={}, state='succeeded'))
        session.add(ApiItem(task_id=tid, source_id=aid, result_id=aid, position=1, state='succeeded'))
        token = issue_session(session, uid)
    sessions, sql = [], []
    def tracked_factory():
        session = factory()
        sessions.append(session)
        return session
    monkeypatch.setattr(db, 'session_factory', lambda: tracked_factory)
    event.listen(engine, 'before_cursor_execute', lambda *args: sql.append(args[2]))
    env = SimpleNamespace(engine=engine, factory=factory, sessions=sessions, sql=sql,
                          data=data, uid=uid, fid=fid, aid=aid, tid=tid, token=token,
                          streams=[], opens=0, fail_open=False, fail_read=False)
    def released():
        assert sessions and not any(s.in_transaction() or s.identity_map for s in sessions)
        assert engine.pool.checkedout() == 0
    env.released = released
    class Source:
        closed = released = False
        def stream(self, size):
            env.released()
            yield data[:5]
            if env.fail_read:
                raise OSError('object read failed')
            env.released()
            yield data[5:]
        def close(self):
            self.closed = True
        def release_conn(self):
            self.released = True
    class Store:
        def stat(self, record):
            env.released()
            if env.fail_open:
                raise OSError('object unavailable')
            return len(data)
        def open(self, record):
            env.released()
            assert isinstance(record, FileDelivery)
            with pytest.raises(FrozenInstanceError):
                record.name = 'changed'
            env.opens += 1
            if env.fail_open:
                raise OSError('object unavailable')
            source = Source()
            env.streams.append(source)
            return source
    app = FastAPI()
    for routes in (router.router, downloads.router, api_router.router):
        app.include_router(routes, prefix='/api/v1')
    app.dependency_overrides[get_store] = Store
    env.app = app
    yield env
    engine.dispose()


def request(env, kind, *, disconnect=False, slow=False, cookie=True, method=None):
    paths = {'cli': f'/files/{env.fid}/content', 'api': f'/api-image-edits/files/{env.aid}/content',
             'cli_zip': '/files/download-zip', 'api_zip': f'/api-image-edits/tasks/{env.tid}/zip'}
    body = json.dumps({'fileIds': [str(env.fid)], 'name': '原图'}).encode() if kind == 'cli_zip' else b''
    headers = [(b'content-type', b'application/json')]
    if cookie:
        headers.append((b'cookie', f'hx_session={env.token}'.encode()))
    scope = {'type': 'http', 'asgi': {'version': '3.0', 'spec_version': '2.4'},
             'http_version': '1.1', 'method': method or ('POST' if body else 'GET'),
             'scheme': 'http', 'path': '/api/v1' + paths[kind], 'query_string': b'',
             'headers': headers, 'server': ('test', 80), 'client': ('test', 1), 'root_path': ''}
    messages = []
    async def receive():
        return {'type': 'http.request', 'body': body, 'more_body': False}
    async def send(message):
        messages.append(message)
        if message['type'] == 'http.response.body' and env.streams:
            env.released()
            before = len(env.sql)
            if slow:
                await asyncio.sleep(.02)
            assert len(env.sql) == before
            if disconnect:
                raise OSError('client disconnected')
    async def run():
        await env.app(scope, receive, send)
    asyncio.run(run())
    return messages[0]['status'], dict(messages[0]['headers']), b''.join(
        m.get('body', b'') for m in messages)


@pytest.mark.parametrize('kind', ['cli', 'api'])
def test_head_checks_storage_after_releasing_database(media_env, kind):
    status, headers, body = request(media_env, kind, method='HEAD')
    assert status == 200 and not body
    assert int(headers[b'content-length']) == len(media_env.data)
    assert media_env.opens == 0
    media_env.fail_open = True
    assert request(media_env, kind, method='HEAD')[0] == 503
    media_env.released()


@pytest.mark.parametrize('kind', ['cli', 'api'])
@pytest.mark.parametrize('method', ['GET', 'HEAD'])
@pytest.mark.parametrize('status', [401, 403, 404, 422, 503])
def test_media_errors_never_cache(media_env, kind, method, status):
    env = media_env
    register_errors(env.app)
    if status in (403, 404):
        with env.factory.begin() as session:
            if status == 403:
                session.get(UserRecord, env.uid).status = 'disabled'
            else:
                session.get(ApiFile if kind == 'api' else FileRecord,
                            env.aid if kind == 'api' else env.fid).status = 'failed'
    elif status == 422:
        env.fid = env.aid = 'not-a-uuid'
    elif status == 503:
        env.fail_open = True
    actual, headers, _ = request(env, kind, method=method, cookie=status != 401)
    assert actual == status
    assert headers[b'cache-control'] == b'private, no-store'


@pytest.mark.parametrize('kind', ['cli', 'api', 'cli_zip', 'api_zip'])
def test_real_dependency_chain_releases_pool_before_io(media_env, kind):
    env = media_env
    status, headers, body = request(env, kind, slow=True)
    assert status == 200 and headers[b'cache-control'] == b'private, no-store'
    assert len(env.sessions) == 1  # Auth and route really used the same yielded Session.
    assert any('auth_sessions' in q for q in env.sql) and any('users' in q for q in env.sql)
    assert all(s.closed and s.released for s in env.streams)
    if 'zip' in kind:
        with ZipFile(BytesIO(body)) as archive:
            assert archive.read(archive.namelist()[0]) == env.data
    else:
        assert body == env.data
    if kind == 'api_zip':
        with env.factory() as session:
            assert session.get(ApiChannel, 1) is not None  # Preserve original commit.


@pytest.mark.parametrize('kind', ['cli', 'api', 'cli_zip', 'api_zip'])
@pytest.mark.parametrize('failure', ['disconnect', 'open', 'read'])
def test_failure_paths_release_pool_and_sources(media_env, kind, failure):
    env = media_env
    env.fail_open, env.fail_read = failure == 'open', failure == 'read'
    if failure == 'open' or (failure == 'read' and kind == 'api_zip'):
        assert request(env, kind)[0] == 503
    else:
        with pytest.raises(Exception):
            request(env, kind, disconnect=failure == 'disconnect')
    env.released()
    assert all(s.closed and s.released for s in env.streams)


@pytest.mark.parametrize('kind', ['cli', 'api', 'cli_zip', 'api_zip'])
def test_each_request_reauthorizes_and_checks_file_eligibility(media_env, kind):
    env = media_env
    assert request(env, kind, cookie=False)[0] == 401
    assert env.opens == 0
    assert request(env, kind)[0] == 200
    with env.factory.begin() as session:
        session.get(UserRecord, env.uid).status = 'disabled'
    opened = env.opens
    assert request(env, kind)[0] == 403 and env.opens == opened
    with env.factory.begin() as session:
        session.get(UserRecord, env.uid).status = 'active'
        session.get(ApiFile if kind.startswith('api') else FileRecord,
                    env.aid if kind.startswith('api') else env.fid).status = 'failed'
    assert request(env, kind)[0] == 404 and env.opens == opened
