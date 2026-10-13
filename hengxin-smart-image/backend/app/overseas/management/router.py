from uuid import UUID
from fastapi import APIRouter, Depends, Query, Request
from starlette.concurrency import run_in_threadpool
from app.modules.files.multipart import parse_upload, UPLOAD_BODY
from app.modules.skills.package_validator import MAX_ZIP
from app.storage.minio_store import get_store
from sqlalchemy.orm import Session
from app.core.browser_auth import browser_request
from app.db.session import get_session
from app.overseas.permissions import require_permission
from . import facts, monitor, settings, skills, usage
from .schemas import SettingsPatch, SkillCreate, SkillPatch, SkillPublish, Stage

router = APIRouter(prefix='/api/overseas/v1/management', tags=['overseas-management'])
stats = require_permission('stats.read')
skill_admin = require_permission('skills.manage')
settings_admin = require_permission('settings.manage')


@router.post('/skill-packages', dependencies=[Depends(browser_request)], status_code=201, openapi_extra=UPLOAD_BODY)
async def upload_package(request: Request, name: str = Query(min_length=1, max_length=100),
                         stage: Stage = 'generation', identity: UUID | None = None,
                         version: int | None = Query(None, ge=1), actor=Depends(skill_admin),
                         session: Session = Depends(get_session), store=Depends(get_store)):
    from .packages import import_package
    from fastapi import HTTPException
    if (identity is None) != (version is None):
        raise HTTPException(422, '更新版本必须同时提供Skill编号与当前版本')
    form, file = await parse_upload(request, MAX_ZIP, maximum=MAX_ZIP, label='Skill ZIP')
    try:
        data = await file.read(MAX_ZIP + 1)
        return await run_in_threadpool(import_package, session, store, actor, data, name, stage, identity, version)
    finally:
        await form.close()


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
