"""Ordinary designers recover selected original bytes without invoking a model."""
from uuid import UUID, uuid5
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.overseas.auth.models import Member
from app.overseas.tasks.models import TaskDeletion
from . import queries, recovery_listing as listing, output_store
from .models import ConversationDeletion, Picture, OutputFile, Turn


def guard(session, actor_id, task_id, conversation_id, *, write=True, idle=True):
    actor = session.scalar(select(Member).where(Member.id == actor_id)
                           .execution_options(populate_existing=True))
    if actor is None:
        raise HTTPException(403, '当前成员无权操作')
    # Task locks serialize reads/publication with new turns, completion and deletion.
    task = queries.access(session, actor, task_id, write=True)
    channel = queries.conversation(session, task.id, conversation_id, writable=True)
    if session.get(TaskDeletion, task.id) or session.get(ConversationDeletion, channel.id):
        raise HTTPException(409, '任务或会话正在删除，不能取回文件')
    if write and task.status != 'studio':
        raise HTTPException(409, '任务已完成或不可修改，请解冻后再取回文件')
    if idle and listing.busy(session, channel):
        raise HTTPException(409, '当前会话尚未停止，请等待执行结束后取回文件')
    return channel


def available(session, actor, task_id, conversation_id):
    channel = guard(session, actor.id, task_id, conversation_id, write=False, idle=False)
    active = listing.busy(session, channel)
    items = listing.candidates(session, channel, mutable=not active)
    return dict(items=[item.dto() for item in items.values()], busy=active)


def existing(session, channel, target, checksum):
    for model, kind in ((Picture, 'picture'), (OutputFile, 'file')):
        row = session.scalar(select(model).join(Turn, Turn.id == model.turn_id).where(
            model.task_id == channel.task_id, Turn.conversation_id == channel.id,
            model.source_path.in_((target, 'sandbox:' + target)), model.checksum == checksum)
            .order_by(model.created_at, model.id).limit(1))
        if row:
            return dict(id=str(row.id), kind=kind)
    return None


def recover(factory, actor_id, task_id, conversation_id, files, store):
    saved, errors = [], []
    # Reject the entire request for authorization/state errors before touching files.
    with factory.begin() as session:
        guard(session, actor_id, task_id, conversation_id)
    for selected in files:
        name = '所选文件'
        try:
            with factory.begin() as session:
                channel = guard(session, actor_id, task_id, conversation_id)
                candidates = listing.candidates(session, channel)
                item = candidates.get(selected.id)
                if item is None:
                    raise listing.RecoveryError('文件已不存在或不属于当前会话，请刷新列表')
                name = item.name
                file = listing.read(item, selected.version)
                # Work and its captured copy are two views of the same turn's original.
                snapshot = item.snapshot or next((candidate.snapshot for candidate in candidates.values()
                    if candidate.snapshot is not None and candidate.job.id == item.job.id
                    and candidate.target == item.target
                    and candidate.snapshot['checksum'] == file.checksum), None)
                previous = (existing(session, channel, item.target, file.checksum)
                            if snapshot is None else None)
                if previous:
                    saved.append(previous)
                    continue
                identity = (UUID(snapshot['pictureId']) if snapshot is not None else
                            uuid5(UUID(item.job.payload['turnId']), item.target + '\n' + file.checksum))
                session.expunge(item.job)
            saved.append(output_store.save(factory, item.job, item.target, file, identity, store,
                lambda db: guard(db, actor_id, task_id, conversation_id)))
        except HTTPException as exc:
            errors.append(dict(id=selected.id, name=name, message=str(exc.detail)))
        except listing.RecoveryError as exc:
            errors.append(dict(id=selected.id, name=name, message=str(exc)))
        except (OSError, ValueError):
            errors.append(dict(id=selected.id, name=name,
                message='文件读取或校验失败，原件可能已删除、覆盖或不可访问，请刷新后重试'))
        except Exception:
            errors.append(dict(id=selected.id, name=name, message='文件保存失败，请稍后重新取回'))
    return dict(saved=saved, errors=errors)


def receive(session, actor, task_id, conversation_id, body, store):
    actor_id = actor.id
    factory = sessionmaker(bind=session.get_bind(), expire_on_commit=False)
    session.rollback()  # Close request/auth read transaction before independent durable saves.
    return recover(factory, actor_id, task_id, conversation_id, body.files, store)
