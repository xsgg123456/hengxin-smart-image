from sqlalchemy.dialects.postgresql import insert

from app.core.config import get_settings
from app.db.session import session_factory
from app.resource_models import UserRecord


def seed_dev_identity():
    settings = get_settings()
    if not settings.enable_dev_identity or settings.app_env == 'production':
        return
    # Never reactivate or reassign an existing account on startup/request.
    with session_factory().begin() as session:
        session.execute(insert(UserRecord).values(
            id=settings.dev_user_id, name=settings.dev_user_name,
            role=settings.dev_user_role, status='active', identity_source='development',
        ).on_conflict_do_nothing(index_elements=['id']))
        user = session.get(UserRecord, settings.dev_user_id)
        if user.identity_source != 'development':
            raise RuntimeError('Development identity conflicts with an existing real identity')
