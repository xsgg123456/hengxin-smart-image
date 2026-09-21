"""Registration and state transitions; filesystem checks belong to the Worker."""
import json
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import Job, Outbox
from app.modules.skills.models import SkillAuditRecord, SkillRecord, SkillVersionRecord
from app.modules.skills.service import dto, get_version


def audit(session, user, action, record):
    session.add(SkillAuditRecord(operator_id=user.id, action=action,
        detail=json.dumps({'id': str(record.id), 'name': record.skill.name,
                           'version': record.version}, ensure_ascii=False)))


def register(session, user, payload):
    try:
        skill = session.scalar(select(SkillRecord).where(
            SkillRecord.name == payload.name, SkillRecord.mode == payload.mode))
        if skill and (skill.catalog_status or skill.removed):
            raise HTTPException(409, '该 Skill 已由目录管理，请使用同步')
        if skill is None:
            skill = SkillRecord(name=payload.name, mode=payload.mode, description=payload.description)
            session.add(skill)
            session.flush()
        record = SkillVersionRecord(id=uuid4(), skill=skill, version=payload.version,
            source_type='local', description=payload.description,
            status='pending', checksum='', bucket=None, object_key=None)
        session.add(record)
        session.flush()
        audit(session, user, 'register', record)
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, '该 Skill 版本已登记或正在登记，请刷新后重试') from None
    return record


def check(session, user, version_id):
    record = get_version(session, version_id, lock=True)
    if record.skill.catalog_status or record.skill.removed:
        raise HTTPException(409, '请通过 Skill 目录同步')
    if record.source_type != 'local':
        raise HTTPException(409, '历史 ZIP 版本请使用安装流程')
    if record.status == 'checking':
        return record
    job_id = uuid4()
    session.add(Job(id=job_id, kind='skill_check', idempotency_key=f'skill-check:{job_id}',
        payload_hash=record.checksum, value=str(record.id), status='queued'))
    session.flush()
    session.add(Outbox(job_id=job_id))
    record.current_job_id, record.status, record.error = job_id, 'checking', None
    audit(session, user, 'check', record)
    session.commit()
    return record


def remove(session, user, version_id):
    record = get_version(session, version_id, lock=True)
    if record.skill.catalog_status or record.skill.removed:
        raise HTTPException(409, '请通过 Skill 目录移除登记')
    if record.source_type != 'local':
        raise HTTPException(409, '历史 ZIP 版本不支持移除登记')
    view = dto(session, record)
    if record.status == 'checking' or view.referenced or view.isDefault:
        raise HTTPException(409, '版本仍被引用或正在检查，不能移除登记')
    job = session.get(Job, record.current_job_id) if record.current_job_id else None
    if job and job.status not in ('succeeded', 'failed', 'cancelled', 'partial'):
        raise HTTPException(409, '检查作业尚未结束')
    audit(session, user, 'unregister', record)
    session.delete(record)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, '版本已被引用，请刷新后重试') from None
