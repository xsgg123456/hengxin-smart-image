from datetime import timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import and_, func, select, update

from app.contracts.business import PageResult, Picture, Template
from app.models import utcnow
from app.modules.auth.permissions import authorize
from app.modules.files.deletions import logical_delete
from app.modules.skills.models import SkillVersionRecord
from app.modules.skills.service import resolve_binding
from app.resource_models import FileRecord
from .models import TemplateImageRecord, TemplateRecord, TemplateVersionRecord


def find_template(session, template_id, *, lock=False):
    query = select(TemplateRecord).where(TemplateRecord.id == template_id,
                                         TemplateRecord.deleted_at.is_(None))
    if lock:
        query = query.with_for_update()
    record = session.scalar(query)
    if record is None:
        raise HTTPException(404, '模板不存在')
    return record


def serialize(session, version):
    images = session.scalars(select(TemplateImageRecord).where(
        TemplateImageRecord.template_version_id == version.id).order_by(TemplateImageRecord.slot)).all()
    skill = session.get(SkillVersionRecord, version.skill_version_id) if version.skill_version_id else None
    created_at = version.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return Template(
        id=str(version.template_id), name=version.name, mode=version.mode,
        images=[Picture(name=item.name, fileId=str(item.file_id),
                        url=f'/api/v1/files/{item.file_id}/content') for item in images],
        skill=version.skill_name, skillVersionId=str(version.skill_version_id) if version.skill_version_id else None,
        skillBinding=version.skill_binding, notes=version.notes,
        updatedAt=created_at.isoformat(), active=bool(version.enabled and skill and skill.status == 'available'),
        version=version.version, ownerId=str(version.owner_id),
    )


def read_current(session, record):
    version = session.scalar(select(TemplateVersionRecord).where(
        TemplateVersionRecord.template_id == record.id, TemplateVersionRecord.version == record.version))
    return serialize(session, version)


def list_templates(session, query):
    version = TemplateVersionRecord
    statement = select(version).join(TemplateRecord, and_(
        TemplateRecord.id == version.template_id, TemplateRecord.version == version.version
    )).where(TemplateRecord.deleted_at.is_(None))
    if query.mode:
        statement = statement.where(version.mode == query.mode)
    if query.search:
        statement = statement.where(version.name.icontains(query.search, autoescape=True))
    if query.activeOnly:
        statement = statement.join(SkillVersionRecord, SkillVersionRecord.id == version.skill_version_id).where(
            version.enabled.is_(True), SkillVersionRecord.status == 'available')
    total = session.scalar(select(func.count()).select_from(statement.subquery()))
    count = select(func.count()).where(TemplateImageRecord.template_version_id == version.id).scalar_subquery()
    order = {'name': version.name.asc(), 'images': count.desc()}.get(query.sort, version.created_at.desc())
    records = session.scalars(statement.order_by(order, version.id).offset(
        (query.page - 1) * query.pageSize).limit(query.pageSize)).all()
    return PageResult[Template](items=[serialize(session, item) for item in records],
                                page=query.page, pageSize=query.pageSize, total=total)


def validate_files(session, body):
    if body.mode not in ('wallpaper', 'product'):
        raise HTTPException(422, '文字处理不使用模板')
    if not body.name.strip() or len(body.name.strip()) > 200:
        raise HTTPException(422, '模板名称须为1至200个字符')
    if not 1 <= len(body.images) <= 20:
        raise HTTPException(422, '模板须包含1至20张图片')
    files = []
    for image in body.images:
        try:
            file_id = UUID(image.fileId)
        except (ValueError, TypeError, AttributeError):
            raise HTTPException(422, '图片必须引用已上传的文件') from None
        record = session.get(FileRecord, file_id)
        if not record or record.status != 'ready' or record.deleted_at is not None:
            raise HTTPException(422, '图片不存在或尚未上传完成')
        files.append(record)
    return files


def save_template(session, user, body, template_id=None):
    authorize(user)
    files = validate_files(session, body)
    skill = resolve_binding(session, body.mode, body.skillVersionId)
    now = utcnow()
    if template_id is None:
        record = TemplateRecord(owner_id=user.id, version=1, created_at=now, updated_at=now)
        session.add(record)
        session.flush()
    else:
        record = find_template(session, template_id)
        if body.expectedVersion is None or body.expectedVersion < 1:
            raise HTTPException(422, '编辑模板必须提供当前版本号')
        changed = session.execute(update(TemplateRecord).where(
            TemplateRecord.id == template_id, TemplateRecord.version == body.expectedVersion,
            TemplateRecord.deleted_at.is_(None)
        ).values(version=body.expectedVersion + 1, updated_at=now).execution_options(synchronize_session=False))
        if changed.rowcount != 1:
            session.rollback()
            raise HTTPException(409, '模板已被其他成员修改，请刷新后重试')
        session.refresh(record)
    version = TemplateVersionRecord(
        template_id=record.id, version=record.version, owner_id=record.owner_id, operator_id=user.id,
        name=body.name.strip(), mode=body.mode, notes=body.notes, enabled=body.active,
        skill_binding='module_default' if body.skillVersionId is None else 'specific',
        skill_version_id=skill.id if skill else None, skill_name=skill.skill.name if skill else '',
        created_at=now, updated_at=now,
    )
    session.add(version)
    session.flush()
    session.add_all([TemplateImageRecord(template_version_id=version.id, file_id=file.id,
                                         slot=slot, name=file.name) for slot, file in enumerate(files)])
    session.commit()
    return serialize(session, version)


def delete_template(session, user, template_id):
    record = find_template(session, template_id, lock=True)
    logical_delete(session, record, 'template', user)
    session.commit()


def list_versions(session, template_id):
    find_template(session, template_id)
    versions = session.scalars(select(TemplateVersionRecord).where(
        TemplateVersionRecord.template_id == template_id).order_by(TemplateVersionRecord.version.desc())).all()
    return [serialize(session, item) for item in versions]
