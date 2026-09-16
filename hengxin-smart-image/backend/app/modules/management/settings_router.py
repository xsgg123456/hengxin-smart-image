from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.contracts.management import ManagedSettings, SettingsInput
from app.db.session import get_session
from app.modules.auth.permissions import require_permission
from .settings import read_settings, save_settings

router = APIRouter(tags=['management'])
Admin = Annotated[object, Depends(require_permission('manage_system'))]
Database = Annotated[Session, Depends(get_session)]


@router.get('/management/settings', response_model=ManagedSettings)
def get_config(user: Admin, session: Database):
    return read_settings(session)


@router.put('/management/settings', response_model=ManagedSettings)
def put_config(body: SettingsInput, user: Admin, session: Database):
    return save_settings(session, user, body)
