from uuid import UUID

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select

from app.contracts.business import Mode
from app.contracts.management import DefaultSkillIds, SkillStatusInput
from app.models import Job
from app.modules.skills.router import Admin, Database, Reader
from app.modules.skills.models import SkillRecord
from app.modules.skills import catalog_service as service

router = APIRouter(tags=['skill-catalog'])


class ModeInput(BaseModel):
    mode: Mode


@router.get('/skill-catalog')
def available(user: Reader, session: Database, mode: Mode | None = None):
    return [service.dto(session, row) for row in session.scalars(select(SkillRecord).where(
        SkillRecord.removed.is_(False))).all() if service.state(session, row) == 'available'
        and (mode is None or row.mode == mode)]


@router.get('/management/skill-catalog')
def listing(user: Admin, session: Database):
    return [service.dto(session, row) for row in session.scalars(select(SkillRecord).where(
        SkillRecord.removed.is_(False)).order_by(SkillRecord.name, SkillRecord.id)).all()]


@router.post('/management/skill-catalog/sync', status_code=202)
def sync(user: Admin, session: Database):
    return service.queue_sync(session, user)


@router.get('/management/skill-catalog/sync')
def sync_status(user: Admin, session: Database):
    return service.sync_state(session)


@router.get('/management/skill-catalog/defaults')
def defaults(user: Admin, session: Database):
    return service.defaults(session)


@router.put('/management/skill-catalog/defaults')
def save_defaults(payload: DefaultSkillIds, user: Admin, session: Database):
    from app.modules.management.settings import save_defaults
    save_defaults(session, user, payload)
    return service.defaults(session)


@router.put('/management/skill-catalog/{skill_id}/mode')
def mode(skill_id: UUID, payload: ModeInput, user: Admin, session: Database):
    from app.modules.management.settings import lock_settings
    lock_settings(session)
    if session.scalar(select(Job.id).where(Job.kind == 'skill_sync',
            Job.status.in_(('queued', 'running'))).limit(1)):
        raise HTTPException(409, '同步进行中，请稍后选择类型')
    row = service.get_skill(session, skill_id)
    if row.catalog_status == 'syncing':
        raise HTTPException(409, '同步进行中，请稍后选择类型')
    if row.mode and row.mode != payload.mode:
        raise HTTPException(409, '已确定的 Skill 类型不能更改，请使用独立 Skill 标识')
    row.mode, row.catalog_status = payload.mode, 'syncing'
    service.audit(session, user, 'catalog_mode', {'id': str(row.id), 'mode': payload.mode})
    service.queue_sync(session, user)
    return service.dto(session, row)


@router.put('/management/skill-catalog/{skill_id}/status')
def status(skill_id: UUID, payload: SkillStatusInput, user: Admin, session: Database):
    return service.set_status(session, user, skill_id, payload.status)


@router.delete('/management/skill-catalog/{skill_id}', status_code=204)
def remove(skill_id: UUID, user: Admin, session: Database):
    service.remove(session, user, skill_id)
    return Response(status_code=204)
