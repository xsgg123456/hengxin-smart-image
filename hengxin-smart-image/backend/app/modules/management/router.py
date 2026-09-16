from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.contracts import management as m
from app.db.session import get_session
from app.modules.auth.dependencies import CurrentUser
from app.modules.management.usage import build_usage

router = APIRouter(tags=['management'])


@router.get('/management/usage', response_model=m.UsageReport)
def usage(
    query: Annotated[m.UsageQuery, Query()],
    user: CurrentUser,
    session: Session = Depends(get_session),
):
    return build_usage(session, user, query)
