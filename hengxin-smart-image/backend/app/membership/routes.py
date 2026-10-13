"""Build identical HTTP contracts while keeping dependencies business-local."""
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.browser_auth import TicketInput, browser_request, redeem_business_ticket
from app.db.session import get_session
from app.membership import service
from app.membership.schemas import ApplicationStatus, Decision


def application_router(prefix, management_prefix, adapter, admin):
    router = APIRouter(tags=['membership'])

    @router.post(prefix + '/access', dependencies=[Depends(browser_request)])
    def access(body: TicketInput, session: Session = Depends(get_session)):
        return service.access(session, adapter, redeem_business_ticket(body.ticket, 'access'))

    @router.post(prefix + '/application', dependencies=[Depends(browser_request)])
    def submit(body: TicketInput, session: Session = Depends(get_session)):
        assertion = redeem_business_ticket(body.ticket, 'application')
        return service.submit(session, adapter, assertion['member'])

    @router.post(prefix + '/application/withdraw', dependencies=[Depends(browser_request)])
    def withdraw(body: TicketInput, session: Session = Depends(get_session)):
        assertion = redeem_business_ticket(body.ticket, 'application')
        return service.withdraw(session, adapter, assertion['member'])

    @router.get(management_prefix)
    def applications(status: ApplicationStatus | None = None, page: int = Query(1, ge=1),
                     page_size: int = Query(20, alias='pageSize', ge=1, le=100),
                     search: str = Query('', max_length=100),
                     actor=Depends(admin), session: Session = Depends(get_session)):
        return service.list_applications(session, adapter, status, page, page_size, search)

    @router.post(management_prefix + '/{application_id}/decision',
                 dependencies=[Depends(browser_request)])
    def decision(application_id: UUID, body: Decision, actor=Depends(admin),
                 session: Session = Depends(get_session)):
        return service.decide(session, adapter, actor, application_id, body)

    return router
