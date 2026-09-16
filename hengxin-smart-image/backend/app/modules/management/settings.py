"""Versioned configuration shared by UI, admission and upload validation."""
import json

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.core.config import get_settings
from app.modules.auth.dingtalk import is_configured
from app.modules.skills.models import ModuleSkillBinding, SkillAuditRecord
from app.modules.skills.service import get_version, resolve_binding
from .models import SettingsAuditRecord, SystemSettings

MODES = ('wallpaper', 'product', 'text')


def values(session):
    env = get_settings()
    row = session.get(SystemSettings, 1)
    config = dict(row.values) if row else {}
    return {
        'version': row.version if row else 1,
        'concurrency': min(config.get('concurrency', env.generation_concurrency), env.generation_concurrency),
        'timeoutSeconds': min(config.get('timeoutSeconds', env.codex_timeout_seconds), env.codex_timeout_seconds),
        'maxUploadBytes': config.get('maxUploadBytes', 10 * 1024**2),
    }


def defaults(session):
    rows = session.scalars(select(ModuleSkillBinding)).all()
    return {mode: next((str(r.skill_version_id) if r.skill_version_id else None
                       for r in rows if r.mode == mode), None) for mode in MODES}


def dingtalk_config():
    env = get_settings()
    return dict(corpId=env.dingtalk_corp_id, appId=env.dingtalk_client_id,
                callbackDomain=env.dingtalk_callback_domain,
                state='ready' if is_configured(env) else 'unconfigured')


def read_settings(session):
    audits = session.scalars(select(SettingsAuditRecord).order_by(
        SettingsAuditRecord.version.desc()).limit(100)).all()
    return {**values(session), 'capacity': get_settings().generation_concurrency,
            'timeoutCapacity': min(3600, get_settings().codex_timeout_seconds),
            'defaultSkillIds': defaults(session), 'dingtalk': dingtalk_config(),
            'audit': [dict(id=str(a.id), operatorId=str(a.operator_id), operatorName=a.operator_name,
                           changedAt=a.created_at.isoformat(), version=a.version, fields=a.fields)
                      for a in audits]}


def _insert(session, model):
    return (sqlite_insert if session.bind.dialect.name == 'sqlite' else pg_insert)(model)


def lock_settings(session):
    session.execute(_insert(session, SystemSettings).values(id=1, version=1, values={})
                    .on_conflict_do_nothing(index_elements=['id']))
    return session.scalar(select(SystemSettings).where(SystemSettings.id == 1)
                          .with_for_update().execution_options(populate_existing=True))


def bind_defaults(session, payload, user):
    for mode in MODES:
        session.execute(_insert(session, ModuleSkillBinding).values(mode=mode)
                        .on_conflict_do_nothing(index_elements=['mode']))
    bindings = {r.mode: r for r in session.scalars(select(ModuleSkillBinding)
                .order_by(ModuleSkillBinding.mode).with_for_update()).all()}
    # Validate every version before changing any binding.
    selected = {}
    for mode in MODES:
        record = resolve_binding(session, mode, payload[mode]) if payload[mode] else None
        if record:
            record = get_version(session, record.id, lock=True)
            if record.status != 'available':
                raise HTTPException(422, '默认 Skill 必须为对应类型的可用版本')
        selected[mode] = record.id if record else None
    for mode in MODES:
        bindings[mode].skill_version_id = selected[mode]
        bindings[mode].operator_id = user.id
    session.add(SkillAuditRecord(operator_id=user.id, action='defaults', detail=json.dumps(payload)))
    session.flush()


def audit(session, row, user, before, after):
    fields = [key for key in after if before.get(key) != after[key]]
    if not fields:
        return
    row.version += 1
    session.add(SettingsAuditRecord(operator_id=user.id, operator_name=user.name,
                version=row.version, before=before, after=after, fields=fields))
    session.flush()


def save_settings(session, user, body):
    row = lock_settings(session)
    if row.version != body.version:
        raise HTTPException(409, '配置已被其他人修改，请重新读取后再保存')
    env = get_settings()
    if body.concurrency > env.generation_concurrency:
        raise HTTPException(422, '并发不能超过已部署 Worker 容量')
    if body.timeoutSeconds > env.codex_timeout_seconds:
        raise HTTPException(422, '超时不能超过部署执行超时上限')
    current_ding = dingtalk_config()
    if body.dingtalk.model_dump() != {k: current_ding[k] for k in ('corpId', 'appId', 'callbackDomain')}:
        raise HTTPException(422, '钉钉标识由部署环境管理，网页仅供查看')
    before = {k: v for k, v in values(session).items() if k != 'version'}
    before['defaultSkillIds'] = defaults(session)
    after = {k: getattr(body, k) for k in ('concurrency', 'timeoutSeconds', 'maxUploadBytes')}
    after['defaultSkillIds'] = body.defaultSkillIds.model_dump()
    if before['defaultSkillIds'] != after['defaultSkillIds']:
        bind_defaults(session, after['defaultSkillIds'], user)
    row.values = {k: after[k] for k in ('concurrency', 'timeoutSeconds', 'maxUploadBytes')}
    audit(session, row, user, before, after)
    session.commit()
    return read_settings(session)


def save_defaults(session, user, payload):
    row = lock_settings(session)
    before = {'defaultSkillIds': defaults(session)}
    after = {'defaultSkillIds': payload.model_dump()}
    if before != after:
        bind_defaults(session, after['defaultSkillIds'], user)
        audit(session, row, user, before, after)
    session.commit()
    return defaults(session)
