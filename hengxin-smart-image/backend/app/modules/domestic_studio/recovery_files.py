"""Retrieve only the owning conversation's existing files on its native node."""
from pathlib import Path
import re
from types import SimpleNamespace
from uuid import UUID, uuid5

from fastapi import HTTPException
from sqlalchemy import select

from app.core.config import get_settings
from app.models import Job
from app.overseas.studio import delivery_snapshot as snapshots, recovery_listing as listing
from app.overseas.studio.delivery_snapshot_fs import canonical_target, root_path, snapshot_path
from app.overseas.studio.files import verify
from app.worker.leases import TERMINAL
from . import conversation_cleanup, delivery_context, maintenance_lock, output_intents, recovery_stream
from .bindings import lock_admission
from .conversation_models import Conversation, ConversationDeletion, Workspace
from .conversation_service import lock_actor, owned
from .runtime import changed
from .turn_models import OutputFile, Picture, Turn


def guard(session, actor_id, conversation_id):
    # This is a per-conversation lock only: model executions in other sessions
    # and the global admission gate stay available during filesystem/storage I/O.
    channel = session.scalar(select(Conversation).where(Conversation.id == conversation_id,
        Conversation.owner_id == actor_id))
    if channel is None:
        raise HTTPException(404, '会话不存在')
    channel = owned(session, actor_id, channel.workspace, conversation_id, lock=True)
    if session.get(ConversationDeletion, channel.id):
        raise HTTPException(409, '会话正在删除，不能取回文件')
    jobs = list(session.execute(select(Turn, Job).join(Job, Turn.job_id == Job.id)
        .where(Turn.conversation_id == channel.id).order_by(Turn.created_at, Turn.id)))
    if any(job.status not in TERMINAL for _, job in jobs):
        raise HTTPException(409, '当前会话尚未停止，请等待执行结束后取回文件')
    if not conversation_cleanup.confirmed(session, channel.id, get_settings()):
        raise HTTPException(409, '原执行状态尚未核实，请稍后重试')
    return channel, jobs


def candidates(channel, jobs):
    root = Path(get_settings().codex_execution_root).absolute() / 'domestic-studio' / str(channel.id)
    owned = [(turn, job) for turn, job in jobs if turn.actor_id == channel.owner_id
             and job.kind == 'domestic_studio' and isinstance(turn.snapshot, dict)
             and turn.snapshot.get('turnId') == str(turn.id)
             and turn.snapshot.get('conversationId') == str(channel.id)]
    if len(owned) != len(jobs):
        raise ValueError('Conversation execution identity mismatch')
    result = {}
    for turn, job in owned:
        control = root / 'control' / str(turn.id) / 'delivery'
        try:
            manifest = snapshots.load(control)
            expected = delivery_context.identity(job.id, channel.owner_id, channel.id, turn.id)
            if not manifest or any(manifest['identity'].get(key) != value for key, value in expected.items()):
                continue
            for item in manifest['items']:
                if item['status'] != 'captured':
                    continue
                target = canonical_target(item['target'])
                identity = str(uuid5(turn.id, 'snapshot:' + target))
                result[identity] = listing.Candidate(identity, job, snapshot_path(root_path(control), item),
                    target, 'snapshot', item['name'], item['sizeBytes'], item['checksum'], dict(item), control)
        except (OSError, ValueError):
            continue
    if not owned:
        return result
    turn, job = owned[-1]
    for item in listing._mutable(root / 'persistent' / 'work', '/work/', 'work', turn, job):
        result[item.id] = item
    linked = {channel.session_id: owned[-1]}
    linked.update({turn.event_session_id: (turn, job) for turn, job in owned if turn.event_session_id})
    for native_id, (turn, job) in linked.items():
        if not isinstance(native_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', native_id):
            continue
        path = root / 'home' / '.codex' / 'generated_images' / native_id
        for item in listing._mutable(path, f'/home/runner/.codex/generated_images/{native_id}/', 'native', turn, job):
            result[item.id] = item
    return result


def authorize(factory, actor_id):
    with factory.begin() as session:
        lock_actor(session, actor_id)


def available(factory, actor_id, conversation_id):
    authorize(factory, actor_id)
    try:
        with factory.begin() as session:
            channel, jobs = guard(session, actor_id, conversation_id)
            items = [item.dto() for item in candidates(channel, jobs).values()]
            lock_actor(session, actor_id)
            return dict(items=items, busy=False)
    except HTTPException as exc:
        if exc.status_code == 409:
            return dict(items=[], busy=True)
        raise


def existing(session, channel, target, checksum):
    for model, kind in ((Picture, 'picture'), (OutputFile, 'file')):
        row = session.scalar(select(model).join(Turn, Turn.id == model.turn_id).where(
            Turn.conversation_id == channel.id, model.source_path.in_((target, 'sandbox:' + target)),
            model.checksum == checksum).order_by(model.created_at, model.id).limit(1))
        if row is not None:
            return row, kind
    return None, None


def save_one(factory, actor_id, conversation_id, selected, store):
    # Native cleanup takes the same OS lock. It remains held if a database
    # connection drops while a storage operation is still in progress.
    with maintenance_lock.hold(get_settings(), conversation_id):
        return _save_one(factory, actor_id, conversation_id, selected, store)


def _save_one(factory, actor_id, conversation_id, selected, store):
    with factory.begin() as session:
        channel, jobs = guard(session, actor_id, conversation_id)
        items = candidates(channel, jobs)
        item = items.get(selected.id)
        if item is None:
            raise listing.RecoveryError('文件已不存在或不属于当前会话，请刷新列表')
        file = recovery_stream.inspect(item, selected.version)
        previous, kind = existing(session, channel, item.target, file.checksum)
        if previous is not None:
            verify(store, previous)
            lock_actor(session, actor_id)
            return dict(id=str(previous.id), kind=kind), item.name
        turn = next((turn for turn, job in jobs if job.id == item.job.id), None)
        if turn is None:
            raise ValueError('Output turn missing')
        matching = item.snapshot or next((candidate.snapshot for candidate in items.values()
            if candidate.snapshot is not None and candidate.job.id == item.job.id
            and candidate.target == item.target and candidate.snapshot['checksum'] == file.checksum), None)
        identity = UUID(matching['pictureId']) if matching else uuid5(turn.id, item.target + '\n' + file.checksum)
        picture = file.width is not None and file.height is not None
        model, other = (Picture, OutputFile) if picture else (OutputFile, Picture)
        if session.get(model, identity) is not None or session.get(other, identity) is not None:
            raise ValueError('Output identity conflict')
        expected = dict(turn_id=turn.id, name=file.name, content_type=file.content_type,
            size_bytes=file.size_bytes, checksum=file.checksum, bucket=get_settings().minio_bucket,
            object_key=f'domestic-studio/outputs/{channel.owner_id}/{channel.workspace}/{channel.id}/{turn.id}/{identity}',
            source_path=item.target)
        if picture:
            expected.update(width=file.width, height=file.height)
        write = output_intents.reserve(turn, identity, expected)
        job_id, target, name = item.job.id, item.target, item.name
    # Keep the intent committed even if the storage request times out or the
    # database connection vanishes while a remote PUT is still in progress.
    with factory.begin() as session:
        channel = session.scalar(select(Conversation).where(Conversation.id == conversation_id,
            Conversation.owner_id == actor_id).with_for_update())
        if channel is None:
            raise ValueError('Conversation is unavailable')
        obj = SimpleNamespace(**expected)
        if write:
            from app.overseas.studio import context_fs as fs
            with fs.reader(file.path) as source:
                store.put_stream(obj, source, file.size_bytes)
        verify(store, obj)
        # Recheck current authorization before publishing. Other same-session
        # writes use NOWAIT and cannot hold the shared gate waiting for this row.
        channel, jobs = guard(session, actor_id, conversation_id)
        lock_actor(session, actor_id)
        lock_admission(session)
        state = session.get(Workspace, (channel.owner_id, channel.workspace))
        if not state or session.get(ConversationDeletion, channel.id):
            raise ValueError('Conversation is unavailable')
        turn = next((turn for turn, job in jobs if job.id == job_id), None)
        if turn is None:
            raise ValueError('Output turn missing')
        previous, kind = existing(session, channel, target, file.checksum)
        if previous is None:
            if session.get(model, identity) is not None or session.get(other, identity) is not None:
                raise ValueError('Output identity conflict')
            session.add(model(id=identity, **expected))
            changed(state, channel, turn)
            previous, kind = SimpleNamespace(id=identity), 'picture' if picture else 'file'
        else:
            verify(store, previous)
        if previous.id == identity:
            output_intents.confirm(turn, identity, expected)
        return dict(id=str(previous.id), kind=kind), name


def recover(factory, actor_id, conversation_id, files, store):
    authorize(factory, actor_id)
    saved, errors = [], []
    for selected in files:
        try:
            value, _ = save_one(factory, actor_id, conversation_id, selected, store)
            saved.append(value)
        except HTTPException as exc:
            errors.append(dict(id=selected.id, name='所选文件', message=str(exc.detail)))
        except listing.RecoveryError as exc:
            errors.append(dict(id=selected.id, name='所选文件', message=str(exc)))
        except Exception:
            errors.append(dict(id=selected.id, name='所选文件', message='文件保存失败，请刷新后重试'))
    return dict(saved=saved, errors=errors)
