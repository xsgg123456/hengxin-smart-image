from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.models import Job, Outbox
from app.modules.skills.models import ModuleSkillBinding, SkillRecord, SkillVersionRecord

UPLOAD_INCOMPLETE = '包上传未完成，请重新上传相同版本包'

def resolve_binding(session, mode, explicit_id, *, allow_unavailable=False):
    from app.modules.skills.catalog_service import current, state
    if explicit_id is not None:
        try:
            identity = session.scalar(select(SkillRecord).where(SkillRecord.id == UUID(str(explicit_id)))
                .with_for_update().execution_options(populate_existing=True))
            record = current(session, identity) if identity else session.get(SkillVersionRecord, UUID(str(explicit_id)))
            if identity and record is None and allow_unavailable:
                record = session.scalar(select(SkillVersionRecord).where(SkillVersionRecord.skill_id == identity.id)
                    .order_by(SkillVersionRecord.created_at.desc()).limit(1))
        except ValueError:
            record = None
        if not record or record.skill.mode != mode:
            raise HTTPException(422, 'Skill 版本不存在或类型不匹配')
        if not identity:
            session.scalar(select(SkillRecord).where(SkillRecord.id == record.skill_id)
                .with_for_update().execution_options(populate_existing=True))
        if record.skill.catalog_status or identity:
            if state(session, record.skill) != 'available' and not allow_unavailable:
                raise HTTPException(422, 'Skill 当前不可用，请先同步或启用')
            record = current(session, record.skill) or record
        if record.skill.removed:
            raise HTTPException(422, 'Skill 已移除登记')
        return record
    binding = session.scalar(select(ModuleSkillBinding).where(ModuleSkillBinding.mode == mode))
    record = session.get(SkillVersionRecord, binding.skill_version_id) if binding and binding.skill_version_id else None
    if record:
        session.scalar(select(SkillRecord).where(SkillRecord.id == record.skill_id)
            .with_for_update().execution_options(populate_existing=True))
        record = current(session, record.skill) if state(session, record.skill) == 'available' else None
    return record if record and record.status == 'available' and record.skill.mode == mode else None


def get_version(session, version_id, lock=False):
    query = select(SkillVersionRecord).where(SkillVersionRecord.id == version_id)
    if lock:
        query = query.with_for_update(of=SkillVersionRecord).execution_options(populate_existing=True)
    record = session.scalar(query)
    if not record:
        raise HTTPException(404, 'Skill 版本不存在')
    return record


def upload_package(session, store, package, data, mode, version):
    skill = session.scalar(select(SkillRecord).where(SkillRecord.name == package.name, SkillRecord.mode == mode))
    if skill is None:
        skill = SkillRecord(name=package.name, mode=mode, description=package.description)
        session.add(skill)
        try:
            session.flush()
        except IntegrityError:
            session.rollback()
            skill = session.scalar(select(SkillRecord).where(SkillRecord.name == package.name, SkillRecord.mode == mode))
    record = SkillVersionRecord(id=uuid4(), skill=skill, version=version, status='failed',
        description=package.description,
        error=UPLOAD_INCOMPLETE, checksum=package.checksum, bucket=get_settings().minio_bucket,
        object_key=f'skills/{uuid4()}.zip', content_type='application/zip')
    session.add(record)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        record = session.scalar(select(SkillVersionRecord).join(SkillRecord).where(
            SkillRecord.name == package.name, SkillRecord.mode == mode,
            SkillVersionRecord.version == version).with_for_update(of=SkillVersionRecord)
            .execution_options(populate_existing=True))
        if not record or record.status != 'failed' or record.error != UPLOAD_INCOMPLETE or record.checksum != package.checksum:
            raise HTTPException(409, '该 Skill 版本已存在；上传失败时只能重传相同内容') from None
    # Serialize completion/re-upload; a failed upload never enters the install queue.
    record = get_version(session, record.id, lock=True)
    if record.status != 'failed' or record.error != UPLOAD_INCOMPLETE:
        raise HTTPException(409, '该 Skill 版本已存在')
    try:
        store.put(record, data)
    except Exception:
        raise HTTPException(503, 'Skill 包存储暂时不可用') from None
    record.status, record.error = 'uploaded', None
    session.commit()
    return record


def install(session, record):
    if record.source_type != 'zip':
        raise HTTPException(409, '本地版本请使用检查部署')
    if record.error == UPLOAD_INCOMPLETE:
        raise HTTPException(409, UPLOAD_INCOMPLETE)
    if record.status == 'installing':
        return record
    if record.status not in ('uploaded', 'failed'):
        raise HTTPException(409, '仅已上传或失败版本可安装')
    job_id = uuid4()
    session.add(Job(id=job_id, kind='skill_install', idempotency_key=f'skill:{job_id}',
        payload_hash=record.checksum, value=str(record.id), status='queued'))
    session.flush()
    session.add(Outbox(job_id=job_id))
    record.current_job_id, record.status, record.error = job_id, 'installing', None
    session.commit()
    return record


def dto(session, record):
    from app.contracts.management import ManagedSkill
    from app.modules.templates.models import TemplateVersionRecord
    referenced = session.scalar(select(TemplateVersionRecord.id).where(
        TemplateVersionRecord.skill_version_id == record.id).limit(1)) is not None
    from app.modules.tasks.models import TaskRecord
    referenced = referenced or session.scalar(select(TaskRecord.id).where(
        TaskRecord.skill_version_id == record.id).limit(1)) is not None
    default = session.scalar(select(ModuleSkillBinding.id).where(
        ModuleSkillBinding.skill_version_id == record.id)) is not None
    return ManagedSkill(id=str(record.id), name=record.skill.name, mode=record.skill.mode,
        sourceType=record.source_type,
        description=record.description if record.description is not None else record.skill.description,
        version=record.version, checksum=record.checksum, status=record.status, isDefault=default,
        installedAt=record.installed_at.isoformat() if record.installed_at else None,
        node=record.node, error=record.error, updatedAt=record.updated_at.isoformat(), referenced=referenced)
