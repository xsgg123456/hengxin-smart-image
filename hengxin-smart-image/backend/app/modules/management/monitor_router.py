from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.contracts.management import MonitorReport
from app.db.session import get_session
from app.modules.auth.dependencies import CurrentUser
from app.modules.management.health import build_monitor

router = APIRouter(tags=['management'])


@router.get('/management/monitor', response_model=MonitorReport, response_model_exclude_unset=True)
def monitor(user: CurrentUser, session: Session = Depends(get_session)):
    return build_monitor(session, user)
