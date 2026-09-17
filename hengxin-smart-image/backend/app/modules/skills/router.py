import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts.business import Mode, SkillVersion
from app.contracts.management import DefaultSkillIds, ManagedSkill, SkillStatusInput, SkillRegisterInput
from app.db.session import get_session
from app.modules.auth.permissions import require_permission
from app.modules.skills.models import ModuleSkillBinding, SkillAuditRecord, SkillRecord, SkillVersionRecord
from app.modules.skills.package_validator import MODES
from app.modules.skills.service import dto, get_version, install
from app.modules.skills import local_service

router = APIRouter(tags=['skills'])
Admin = Annotated[object, Depends(require_permission('manage_system'))]
Reader = Annotated[object, Depends(require_permission('shared_resources'))]
Database = Annotated[Session, Depends(get_session)]


@router.get('/skills', response_model=list[SkillVersion])
def catalog(user: Reader, session: Database, mode: Mode | None = None):
    query = select(SkillVersionRecord).join(SkillRecord).where(SkillVersionRecord.status == 'available')
    if mode:
        query = query.where(SkillRecord.mode == mode)
    return [dto(session, record) for record in session.scalars(query.order_by(SkillVersionRecord.created_at.desc())).all()]


@router.get('/management/skills', response_model=list[ManagedSkill])
def listing(user: Admin, session: Database):
    return [dto(session, record) for record in session.scalars(select(SkillVersionRecord).order_by(SkillVersionRecord.created_at.desc())).all()]


@router.post('/management/skills', status_code=410)
def upload(user: Admin):
    raise HTTPException(410, '网页 ZIP 上传已停用，请人工部署后登记本地版本')


@router.post('/management/skills/register', response_model=ManagedSkill, status_code=201)
def register(payload: SkillRegisterInput, user: Admin, session: Database):
    return dto(session, local_service.register(session, user, payload))


@router.post('/management/skills/{version_id}/check', response_model=ManagedSkill)
def check(version_id: UUID, user: Admin, session: Database):
    return dto(session, local_service.check(session, user, version_id))


@router.delete('/management/skills/{version_id}', status_code=204)
def remove(version_id: UUID, user: Admin, session: Database):
    local_service.remove(session, user, version_id)
    return Response(status_code=204)


@router.get('/management/skills/defaults', response_model=DefaultSkillIds)
def defaults(user: Admin, session: Database):
    rows = session.scalars(select(ModuleSkillBinding)).all()
    return {mode: next((str(r.skill_version_id) if r.skill_version_id else None for r in rows if r.mode == mode), None) for mode in MODES}


@router.put('/management/skills/defaults', response_model=DefaultSkillIds)
def save_defaults(payload: DefaultSkillIds, user: Admin, session: Database):
    from app.modules.management.settings import save_defaults as save_versioned_defaults
    return save_versioned_defaults(session, user, payload)


@router.post('/management/skills/{version_id}/install', response_model=ManagedSkill)
def start_install(version_id: UUID, user: Admin, session: Database):
    return dto(session, install(session, get_version(session, version_id, lock=True)))


@router.put('/management/skills/{version_id}/status', response_model=ManagedSkill)
def status(version_id: UUID, payload: SkillStatusInput, user: Admin, session: Database):
    record = get_version(session, version_id, lock=True)
    allowed = ('verified', 'available', 'disabled') if record.source_type == 'local' else ('available', 'disabled')
    if record.status not in allowed or not record.installed_path or not record.checksum:
        raise HTTPException(409, '只有检查或安装完成的版本可启停')
    record.status = payload.status
    session.add(SkillAuditRecord(operator_id=user.id, action='status',
                                detail=json.dumps({'id': str(record.id), 'status': payload.status})))
    session.commit()
    return dto(session, record)
