"""Stable identities over automatically retained immutable execution snapshots."""
import json
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import select

from app.models import Job, Outbox
from app.modules.skills.models import ModuleSkillBinding, SkillAuditRecord, SkillRecord, SkillVersionRecord


def current(session, skill):
    if skill.current_version_id:
        return session.get(SkillVersionRecord, skill.current_version_id)
    return session.scalar(select(SkillVersionRecord).where(SkillVersionRecord.skill_id == skill.id,
        SkillVersionRecord.status == 'available').order_by(SkillVersionRecord.created_at.desc()).limit(1))


def state(session, skill):
    if skill.removed:
        return 'invalid'
    if skill.catalog_status:
        return skill.catalog_status
    version = current(session, skill)
    if version:
        return 'available'
    disabled = session.scalar(select(SkillVersionRecord.id).where(
        SkillVersionRecord.skill_id == skill.id, SkillVersionRecord.status == 'disabled').limit(1))
    return 'disabled' if disabled else 'invalid'


def get_skill(session, skill_id):
    row = session.scalar(select(SkillRecord).where(SkillRecord.id == skill_id)
        .with_for_update().execution_options(populate_existing=True))
    if not row or row.removed:
        raise HTTPException(404, 'Skill 不存在')
    return row


def references(session, skill):
    from app.modules.templates.models import TemplateRecord, TemplateVersionRecord
    versions = select(SkillVersionRecord.id).where(SkillVersionRecord.skill_id == skill.id)
    default = session.scalar(select(ModuleSkillBinding.id).where(
        ModuleSkillBinding.skill_version_id.in_(versions)).limit(1)) is not None
    template = session.scalar(select(TemplateVersionRecord.id).join(TemplateRecord).where(
        TemplateRecord.deleted_at.is_(None), TemplateRecord.version == TemplateVersionRecord.version,
        TemplateVersionRecord.skill_version_id.in_(versions)).limit(1)) is not None
    return default, template


def dto(session, skill):
    default, referenced = references(session, skill)
    return dict(id=str(skill.id), name=skill.name, description=skill.description,
        mode=skill.mode or None, status=state(session, skill), isDefault=default,
        error=skill.catalog_error, updatedAt=skill.updated_at.isoformat(), referenced=default or referenced)


def audit(session, user, action, detail):
    session.add(SkillAuditRecord(operator_id=user.id, action=action,
        detail=json.dumps(detail, ensure_ascii=False)))


def sync_state(session):
    job = session.scalar(select(Job).where(Job.kind == 'skill_sync').order_by(Job.created_at.desc()).limit(1))
    return dict(jobId=str(job.id) if job else None, status=job.status if job else 'idle', error=job.error if job else None)


def queue_sync(session, user):
    # A persistent singleton row serializes API requests across processes/databases.
    from app.modules.management.settings import lock_settings
    lock_settings(session)
    job = session.scalar(select(Job).where(Job.kind == 'skill_sync', Job.status.in_(('queued', 'running')))
        .order_by(Job.created_at.desc()).limit(1))
    if not job:
        job = Job(id=uuid4(), kind='skill_sync', idempotency_key='skill-sync:' + str(uuid4()),
                  payload_hash='', value='', status='queued')
        session.add(job)
        session.flush()
        session.add(Outbox(job_id=job.id))
        audit(session, user, 'catalog_sync', {'jobId': str(job.id)})
    session.commit()
    return dict(jobId=str(job.id), status=job.status)


def defaults(session):
    result = dict(wallpaper=None, product=None, text=None)
    for binding in session.scalars(select(ModuleSkillBinding)):
        record = session.get(SkillVersionRecord, binding.skill_version_id) if binding.skill_version_id else None
        if record:
            result[binding.mode] = str(record.skill_id)
    return result


def set_status(session, user, skill_id, status):
    row = get_skill(session, skill_id)
    version = current(session, row)
    if state(session, row) not in ('available', 'disabled') or not version:
        # Legacy disabled identities have no selected current version yet.
        version = session.scalar(select(SkillVersionRecord).where(SkillVersionRecord.skill_id == row.id,
            SkillVersionRecord.status == 'disabled').order_by(SkillVersionRecord.created_at.desc()).limit(1))
        if not version or row.catalog_status not in (None, 'disabled'):
            raise HTTPException(409, '请先成功同步 Skill')
    row.current_version_id = version.id
    row.manually_disabled = status == 'disabled'
    row.catalog_status = status
    version.status = status
    audit(session, user, 'catalog_status', {'id': str(row.id), 'status': status})
    session.commit()
    return dto(session, row)


def remove(session, user, skill_id):
    from app.modules.management.settings import lock_settings
    lock_settings(session)
    row = get_skill(session, skill_id)
    if any(references(session, row)):
        raise HTTPException(409, '请先解除模板或模块默认引用')
    if session.scalar(select(Job.id).where(Job.kind == 'skill_sync', Job.status.in_(('queued', 'running'))).limit(1)):
        raise HTTPException(409, '同步进行中，请稍后移除')
    row.removed = True
    audit(session, user, 'catalog_remove', {'id': str(row.id)})
    session.commit()
