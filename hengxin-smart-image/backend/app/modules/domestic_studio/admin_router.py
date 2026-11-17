"""Super-admin-only observation; no owner writes or executor calls are exposed."""
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.modules.auth.application_models import MemberAudit
from app.modules.auth.permissions import require_permission
from app.modules.files.delivery import FileDelivery
from app.overseas.attachment_delivery import deliver
from app.storage.minio_store import get_store
from . import admin_details, admin_queries

router = APIRouter(prefix='/management/domestic-studio/sessions', tags=['domestic-studio-admin'])
Admin = Annotated[object, Depends(require_permission('manage_system'))]
Database = Annotated[Session, Depends(get_session)]
Workspace = Literal['camera', 'case', 'product', 'scene', 'phone']
Status = Literal['empty', 'queued', 'running', 'succeeded', 'failed', 'cancelled', 'unknown']


def audit(session, actor, member_id, action, **objects):
    # Reuse the domestic durable access/audit ledger; never copy conversation text.
    session.add(MemberAudit(actor_id=actor.id, member_id=member_id, action=action,
                            before={}, after=objects))
    session.commit()


@router.get('')
def listing(actor: Admin, session: Database, response: Response, ownerId: UUID | None = None,
            workspace: Workspace | None = None, status: Status | None = None,
            search: str = Query('', max_length=200), page: int = Query(1, ge=1),
            pageSize: int = Query(20, ge=1, le=100)):
    result = admin_queries.listing(session, owner_id=ownerId, workspace=workspace, status=status,
                                  search=search, page=page, page_size=pageSize)
    audit(session, actor, actor.id, 'studio_list', ownerId=str(ownerId) if ownerId else None,
          workspace=workspace, status=status, page=page, pageSize=pageSize)
    response.headers['Cache-Control'] = 'private, no-store'
    return result


@router.get('/{conversation_id}')
def detail(conversation_id: UUID, actor: Admin, session: Database, response: Response):
    channel = admin_queries.conversation(session, conversation_id)
    result = admin_details.detail(session, channel)
    audit(session, actor, channel.owner_id, 'studio_view', conversationId=str(channel.id))
    response.headers['Cache-Control'] = 'private, no-store'
    return result


@router.get('/{conversation_id}/transcript')
def transcript(conversation_id: UUID, actor: Admin, session: Database, response: Response,
               after: int = Query(0, ge=0)):
    channel = admin_queries.conversation(session, conversation_id)
    result = admin_details.transcript(session, channel, after)
    audit(session, actor, channel.owner_id, 'studio_transcript', conversationId=str(channel.id))
    response.headers['Cache-Control'] = 'private, no-store'
    return result


@router.get('/{conversation_id}/{kind}/{file_id}/content')
@router.head('/{conversation_id}/{kind}/{file_id}/content')
def content(conversation_id: UUID, kind: str, file_id: UUID, request: Request,
            actor: Admin, session: Database, preview: bool = False, thumbnail: bool = False,
            store=Depends(get_store)):
    channel = admin_queries.conversation(session, conversation_id)
    row = admin_details.file_row(session, channel.id, kind, file_id)
    captured = FileDelivery.capture(row)
    audit(session, actor, channel.owner_id, 'studio_download', conversationId=str(channel.id),
          fileId=str(file_id), kind=kind, operation='preview' if preview or thumbnail else 'download')
    session.close()
    response = deliver(store, captured, head=request.method == 'HEAD', preview=preview or kind == 'pictures',
                       thumbnail=thumbnail, if_none_match=request.headers.get('if-none-match'))
    response.headers['Cache-Control'] = 'private, no-store'
    return response
