from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import ValidationError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from app.core.browser_auth import browser_request
from app.db.session import get_session
from app.modules.files.validation import validate_image
from app.overseas.auth.dependencies import CurrentMember
from app.overseas.auth.models import Member
from app.overseas.permissions import require_permission
from . import service
from .form import FEEDBACK_BODY, SCREENSHOT_LIMIT, parse_form
from .schemas import CreateFeedback, Status, UpdateFeedback

def private_response(response: Response):
    response.headers['Cache-Control'] = 'private, no-store'


router = APIRouter(prefix='/api/overseas/v1', tags=['overseas-feedback'],
                   dependencies=[Depends(private_response)])
Database = Annotated[Session, Depends(get_session)]
Manager = Annotated[Member, Depends(require_permission('feedback.manage'))]
Offset = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(ge=1, le=100)]


@router.post('/feedback', status_code=201, dependencies=[Depends(browser_request)], openapi_extra=FEEDBACK_BODY)
async def create(request: Request, actor: CurrentMember, session: Database):
    actor_id = actor.id
    await run_in_threadpool(session.commit)
    form = await parse_form(request)
    try:
        fields = dict(form)
        if len(fields) != len(form.multi_items()):
            raise HTTPException(422, '反馈字段不能重复')
        screenshot = fields.pop('screenshot', None)
        if screenshot is not None and not isinstance(screenshot, UploadFile):
            raise HTTPException(422, '请上传截图文件')
        try:
            body = CreateFeedback.model_validate(fields)
        except ValidationError as error:
            raise HTTPException(422, '请检查反馈内容、来源、任务名称及 SKU') from error
        image = await run_in_threadpool(validate_image, screenshot, SCREENSHOT_LIMIT) if screenshot else None
        return await run_in_threadpool(service.create, session, actor_id, body, image)
    finally:
        await form.close()


@router.get('/feedback/mine')
def mine(actor: CurrentMember, session: Database, offset: Offset = 0, limit: Limit = 50):
    return service.listing(session, actor, offset, limit)


@router.get('/feedback/{identifier}/screenshot')
def screenshot(identifier: UUID, actor: CurrentMember, session: Database):
    data, media_type = service.screenshot(session, actor, identifier)
    return Response(data, media_type=media_type, headers={
        'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff'})


@router.get('/management/feedback')
def management(actor: Manager, session: Database, status: Status | None = None,
               offset: Offset = 0, limit: Limit = 50):
    return service.listing(session, actor, offset, limit, management=True, status=status)


@router.get('/management/feedback/{identifier}')
def detail(identifier: UUID, actor: Manager, session: Database):
    return service.describe(service.get(session, identifier), management=True)


@router.patch('/management/feedback/{identifier}', dependencies=[Depends(browser_request)])
def update(identifier: UUID, body: UpdateFeedback, actor: Manager, session: Database):
    return service.change(session, actor, identifier, body)
