"""Serialize frozen owners before admission, preserving only their own Skill bytes."""
import os
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select
from app.core.config import get_settings
from app.overseas.execution.models import Job, TERMINAL
from app.overseas.execution.queue import lock_gate
from app.overseas.execution import skill_history
from app.overseas.studio.models import Turn, Conversation, ConversationDeletion
from app.overseas.studio import context_fs as fs
from app.overseas.tasks.models import Task, TaskDeletion
from . import installed_catalog as catalog


def references(session, names):
    return [job for job in session.scalars(select(Job).execution_options(populate_existing=True))
            if isinstance(job.payload, dict) and isinstance(job.payload.get('skill'), dict)
            and job.payload['skill'].get('name') in names and job.payload['skill'].get('installedRelease')]


def busy(job):
    return job.status not in TERMINAL or (job.process_id is not None and not job.process_exited)


def locked(session, names, *, deleting=False):
    # Same permissions -> Task -> admission order as submission and task erasure.
    initial = references(session, names)
    task_ids = {job.task_id for job in initial}
    for identity in sorted(task_ids, key=str):
        task = session.scalar(select(Task).where(Task.id == identity).with_for_update(skip_locked=True))
        if not task or session.get(TaskDeletion, identity):
            raise HTTPException(409, '关联任务正在变更或删除，请稍后重试')
    lock_gate(session)
    jobs = references(session, names)
    if any(job.task_id not in task_ids for job in jobs):
        raise HTTPException(409, '技能引用刚刚发生变化，请重试')
    if deleting and any(busy(job) for job in jobs):
        raise HTTPException(409, '仍有排队或运行中的任务使用此 Skill，任务结束后才能删除')
    return jobs


def execution_root():
    settings = get_settings()
    root = Path(settings.codex_execution_root).absolute()
    if settings.app_env == 'production' and str(root) != '/var/lib/hengxin-overseas/execution':
        raise ValueError('Wrong overseas history root')
    return fs.checked(root, directory=True)


def owners(session, jobs, *, deduplicate=True):
    """Validate ownership; retain every Job's frozen release when auditing inputs."""
    if not jobs:
        return []
    root = execution_root()
    turns = {row.job_id: row for row in session.scalars(select(Turn).where(Turn.job_id.in_([j.id for j in jobs])))}
    found = {}
    for job in jobs:
        if busy(job):
            continue
        turn = turns.get(job.id)
        if job.kind == 'studio':
            if not turn or turn.task_id != job.task_id:
                raise ValueError('Historical Studio job has no owned turn')
            channel = session.get(Conversation, turn.conversation_id)
            if (not channel or channel.task_id != job.task_id
                    or session.get(ConversationDeletion, channel.id)
                    or job.payload.get('conversationId') != str(channel.id)):
                raise HTTPException(409, '历史会话正在变更或删除，请稍后重试')
            base = fs.checked(root / 'studio', missing=True, directory=True)
            owner = base / str(channel.id)
            if not owner.exists() and channel.session_id:
                raise ValueError('Existing session owner directory is missing')
        else:
            base, owner = root, root / str(job.id)
        skill = job.payload['skill']
        key = (str(owner), skill['name'], skill['checksum']) if deduplicate else job.id
        found[key] = (base, owner, skill)
    return list(found.values())


def preserve(session, jobs):
    from .skill_cleanup import allocated
    added = 0
    for base, owner, skill in owners(session, jobs):
        _, item, _ = catalog.frozen_item(skill)
        # A cancelled-before-start job can legitimately have no filesystem yet.
        ancestor = base if base.exists() else base.parent
        identity = fs.checked(ancestor, directory=True).stat()
        tracked = [base, owner, owner / '.context-prepare.lock']
        def footprint():
            sizes = []
            for path in tracked:
                if path.exists():
                    info = path.lstat()
                    sizes.append(info.st_blocks * 512 if os.name == 'posix' else
                                 (info.st_size if path.is_file() else 0))
            return sum(sizes) + allocated(owner / 'skill-history')
        before = footprint()
        skill_history._directory(base, identity.st_uid, identity.st_gid)
        skill_history._directory(owner, identity.st_uid, identity.st_gid)
        with fs.lock(owner):
            if os.name == 'posix' and os.geteuid() == 0:
                owner_info = owner.stat()
                os.chown(owner / '.context-prepare.lock', owner_info.st_uid, owner_info.st_gid)
            package = None
            def read_source(name):
                nonlocal package
                if package is None:
                    package = catalog.frozen_package(skill)
                return package.files[name]
            # Existing copies (including a previous failed attempt) must also be durable now.
            skill_history.preserve(owner, item, read_source)
        added += max(0, footprint() - before)
    return added


def active_keys(jobs):
    return {(j.payload['skill']['name'], j.payload['skill']['checksum']) for j in jobs if busy(j)}
