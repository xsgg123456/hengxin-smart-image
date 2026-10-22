from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import select
from app.core.config import get_settings
from app.db.timestamps import utcnow
from app.overseas.execution.queue import lock_gate
from app.overseas.tasks.service import lock_actor
from .models import Audit, Settings, Skill
from .installed_catalog import freeze as freeze_installed
from .skills import require_enabled

STAGES = ('analysis', 'generation', 'revision')


def values(session):
    env = get_settings()
    row = session.scalar(select(Settings).where(Settings.id == 1).execution_options(populate_existing=True))
    config = row.values if row else {}
    return {'version': row.version if row else 1, 'paused': config.get('paused', False),
        'concurrency': min(config.get('concurrency', env.generation_concurrency), env.generation_concurrency, 5),
        'timeoutSeconds': min(config.get('timeoutSeconds', env.codex_timeout_seconds), env.codex_timeout_seconds),
        'defaults': {stage: config.get('defaults', {}).get(stage) for stage in STAGES}, 'autoCleanup': False}


def selected(session, identity, stage=None):
    # Old configured UUIDs are resolved by name, but only when truly installed.
    legacy = session.get(Skill, UUID(str(identity)))
    frozen = freeze_installed(identity, legacy.name if legacy else None)
    require_enabled(session, frozen['name'])
    return frozen


def save(session, actor, body):
    actor = lock_actor(session, actor, 'settings.manage')
    gate = lock_gate(session)
    row = session.scalar(select(Settings).where(Settings.id == 1)
                         .execution_options(populate_existing=True))
    before = values(session)
    if before['version'] != body.version:
        raise HTTPException(409, '配置已被修改，请刷新后重试')
    env = get_settings()
    if body.concurrency > env.generation_concurrency or body.timeoutSeconds > env.codex_timeout_seconds:
        raise HTTPException(422, '配置不能超过部署执行容量或超时上限')
    for stage, identity in body.defaults.model_dump().items():
        if identity:
            selected(session, identity, stage)
    if row is None:
        row = Settings(id=1, version=1)
        session.add(row)
    row.version += 1
    row.values = body.model_dump(mode='json', exclude={'version'})
    row.updated_at = utcnow()
    gate.paused = body.paused
    session.flush()
    after = values(session)
    session.add(Audit(actor_id=actor.id, action='settings.update', target='1', before=before, after=after))
    session.commit()
    return after


def freeze(session, stage, builtin):
    lock_gate(session)
    config = values(session)
    identity = config['defaults'][stage]
    skill = selected(session, identity, stage) if identity else builtin
    return {'skill': skill, 'runtime': {'timeoutSeconds': config['timeoutSeconds']}}


def freeze_selected(session, identity):
    """Freeze an immutable complete installation, preserving old queued payloads."""
    lock_gate(session)
    config = values(session)
    skill = selected(session, identity) if identity else None
    return {'skill': skill, 'runtime': {'timeoutSeconds': config['timeoutSeconds']}}
