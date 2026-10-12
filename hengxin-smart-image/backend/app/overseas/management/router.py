from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.browser_auth import browser_request
from app.db.session import get_session
from app.overseas.permissions import require_permission
from . import facts, monitor, settings, skills, usage
from .schemas import SettingsPatch, SkillCreate, SkillPatch, SkillPublish

router = APIRouter(prefix='/api/overseas/v1/management', tags=['overseas-management'])
stats = require_permission('stats.read')
skill_admin = require_permission('skills.manage')
settings_admin = require_permission('settings.manage')


@router.get('/usage')
def read_usage(actor=Depends(stats), session: Session = Depends(get_session), clauses=Depends(facts.filters)):
    return usage.read(session, actor, clauses)


@router.get('/jobs')
def read_jobs(actor=Depends(stats), session: Session = Depends(get_session), clauses=Depends(facts.filters),
              page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=100)):
    return monitor.read(session, actor, clauses, page, pageSize)


@router.get('/skills')
def read_skills(actor=Depends(skill_admin), session: Session = Depends(get_session)):
    return skills.list_skills(session)


@router.post('/skills', dependencies=[Depends(browser_request)], status_code=201)
def create_skill(body: SkillCreate, actor=Depends(skill_admin), session: Session = Depends(get_session)):
    return skills.mutate(session, actor, body)


@router.post('/skills/{identity}/versions', dependencies=[Depends(browser_request)])
def publish(identity: UUID, body: SkillPublish, actor=Depends(skill_admin), session: Session = Depends(get_session)):
    return skills.mutate(session, actor, body, identity, publish=True)


@router.patch('/skills/{identity}', dependencies=[Depends(browser_request)])
def patch_skill(identity: UUID, body: SkillPatch, actor=Depends(skill_admin), session: Session = Depends(get_session)):
    return skills.mutate(session, actor, body, identity)


@router.get('/settings')
def read_settings(actor=Depends(settings_admin), session: Session = Depends(get_session)):
    return settings.values(session)


@router.patch('/settings', dependencies=[Depends(browser_request)])
def patch_settings(body: SettingsPatch, actor=Depends(settings_admin), session: Session = Depends(get_session)):
    return settings.save(session, actor, body)
