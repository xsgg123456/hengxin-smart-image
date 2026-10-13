from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.browser_auth import browser_request
from app.db.session import get_session
from app.overseas.auth.models import Member
from app.overseas.members import service
from app.overseas.members.schemas import MemberPatch, Role, Status
from app.overseas.permissions import require_permission
from app.membership.schemas import Directory

router = APIRouter(prefix='/api/overseas/v1/members', tags=['overseas-members'])
admin = require_permission('members.manage')


@router.get('')
def members(search: str = Query('', max_length=100), status: Status | None = None,
            role: Role | None = None, page: int = Query(1, ge=1),
            page_size: int = Query(20, alias='pageSize', ge=1, le=100),
            directory: Directory = 'members',
            actor: Member = Depends(admin), session: Session = Depends(get_session)):
    return service.list_members(session, search, status, role, page, page_size, directory)


@router.get('/{member_id}')
def detail(member_id: UUID, actor: Member = Depends(admin), session: Session = Depends(get_session)):
    return service.describe(session, service.get_member(session, member_id))


@router.patch('/{member_id}', dependencies=[Depends(browser_request)])
def patch(member_id: UUID, body: MemberPatch, actor: Member = Depends(admin),
          session: Session = Depends(get_session)):
    return service.patch_member(session, actor, member_id, body)


@router.get('/{member_id}/audit')
def audit(member_id: UUID, actor: Member = Depends(admin), session: Session = Depends(get_session)):
    return service.audit_entries(session, member_id)
