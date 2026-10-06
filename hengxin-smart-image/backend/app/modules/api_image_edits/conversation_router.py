import asyncio
import json
from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool
from starlette.responses import StreamingResponse
from app.db.session import session_factory
from app.modules.auth.dependencies import get_current_user, get_identity_id
from app.modules.auth.permissions import authorize
from . import conversation as service
from .conversation_models import ConversationEvent
from .router import Database, Key, User

router = APIRouter(prefix='/api-image-edits/tasks/{task_id}/items/{item_id}/conversation')


@router.get('')
def detail(task_id: UUID, item_id: UUID, user: User, session: Database):
    result = service.view(session, task_id, item_id)
    session.commit()
    return result


@router.post('/turns', status_code=202)
def submit(task_id: UUID, item_id: UUID, data: service.SubmitTurn, user: User, session: Database, key: Key):
    service.submit(session, user, task_id, item_id, data, key)
    return service.view(session, task_id, item_id)


@router.post('/turns/{turn_id}/stop')
def stop(task_id: UUID, item_id: UUID, turn_id: UUID, user: User, session: Database):
    service.stop(session, task_id, item_id, turn_id)
    return service.view(session, task_id, item_id)


@router.post('/turns/{turn_id}/adopt')
def adopt(task_id: UUID, item_id: UUID, turn_id: UUID, data: service.AdoptTurn,
          user: User, session: Database, key: Key):
    service.adopt(session, user, task_id, item_id, turn_id, data, key)
    return service.view(session, task_id, item_id)


def read_events(factory, identity_id, task_id, item_id, after):
    with factory() as session:
        authorize(get_current_user(identity_id, session))
        _, item = service.target(session, task_id, item_id)
        conversation = service.identity(session, item.id)
        if not conversation:
            return []
        return list(session.scalars(select(ConversationEvent.payload).where(
            ConversationEvent.conversation_id == conversation.id,
            ConversationEvent.number > after).order_by(ConversationEvent.number).limit(100)))


@router.get('/events')
async def events(task_id: UUID, item_id: UUID, request: Request,
                 identity_id=Depends(get_identity_id), after: int = Query(0, ge=0),
                 last_id: Annotated[str | None, Header(alias='Last-Event-ID')] = None):
    if last_id is not None:
        if not last_id.isdecimal() or len(last_id) > 18:
            raise HTTPException(422, '事件游标无效')
        after = max(after, int(last_id))
    factory = session_factory()
    initial = await run_in_threadpool(read_events, factory, identity_id, task_id, item_id, after)
    async def stream():
        cursor, batch, ticks = after, initial, 0
        while not await request.is_disconnected():
            for event in batch:
                cursor = event['id']
                yield f'id: {cursor}\nevent: message\ndata: {json.dumps(event, ensure_ascii=False)}\n\n'
            if ticks % 10 == 0:
                yield ': heartbeat\n\n'
            await asyncio.sleep(1)
            ticks += 1
            try:
                batch = await run_in_threadpool(read_events, factory, identity_id, task_id, item_id, cursor)
            except HTTPException:
                yield 'event: closed\ndata: {"reason":"access_changed"}\n\n'
                return
    return StreamingResponse(stream(), media_type='text/event-stream', headers={
        'Cache-Control': 'private, no-store', 'X-Accel-Buffering': 'no'})
