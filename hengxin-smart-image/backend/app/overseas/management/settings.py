from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import select
from app.core.config import get_settings
from app.db.timestamps import utcnow
from app.overseas.execution.queue import lock_gate
from app.overseas.tasks.service import lock_actor
from .models import Audit, Settings, Skill, SkillVersion

STAGES = ('analysis', 'generation', 'revision')


def values(session):
    env = get_settings()
    row = session.scalar(select(Settings).where(Settings.id == 1).execution_options(populate_existing=True))
    config = row.values if row else {}
    return {'version': row.version if row else 1, 'paused': config.get('paused', False),
        'concurrency': min(config.get('concurrency', env.generation_concurrency), env.generation_concurrency, 5),
        'timeoutSeconds': min(config.get('timeoutSeconds', env.codex_timeout_seconds), env.codex_timeout_seconds),
        'defaults': {stage: config.get('defaults', {}).get(stage) for stage in STAGES}, 'autoCleanup': False}


def selected(session, identity, stage):
    skill = session.scalar(select(Skill).where(Skill.id == UUID(str(identity)))
                           .execution_options(populate_existing=True))
    if skill is None or not skill.enabled or skill.stage != stage:
        raise HTTPException(422, '默认 Skill 必须存在、启用并匹配执行阶段')
    return skill


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
    # All writers and frozen reads share the existing gate. Lock order remains task -> gate -> job.
    lock_gate(session)
    config = values(session)
    identity = config['defaults'][stage]
    skill = builtin
    if identity:
        record = selected(session, identity, stage)
        version = session.scalar(select(SkillVersion).where(SkillVersion.skill_id == record.id,
                                                           SkillVersion.version == record.current_version))
        skill = {'id': str(record.id), 'name': record.name, 'version': version.version, 'files': version.files, 'assets': version.assets or {}}
    return {'skill': skill, 'runtime': {'timeoutSeconds': config['timeoutSeconds']}}


def freeze_selected(session, identity):
    """Freeze the designer-selected version without imposing legacy stage routing."""
    lock_gate(session)
    config = values(session)
    skill = None
    if identity:
        record = session.get(Skill, UUID(str(identity)))
        if record is None or not record.enabled:
            raise HTTPException(422, '所选 Skill 已停用或不存在，请重新选择')
        version = session.scalar(select(SkillVersion).where(SkillVersion.skill_id == record.id,
                                                           SkillVersion.version == record.current_version))
        if version is None:
            raise HTTPException(409, 'Skill 版本缺失，请联系管理员')
        skill = {'id': str(record.id), 'name': record.name, 'version': version.version,
                 'files': version.files, 'assets': version.assets or {}}
    return {'skill': skill, 'runtime': {'timeoutSeconds': config['timeoutSeconds']}}
