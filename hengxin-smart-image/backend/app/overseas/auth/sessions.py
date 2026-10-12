"""Only the overseas session table participates in these operations."""
from app.core.config import get_settings
from app.identity.session_records import issue, resolve, revoke
from app.overseas.auth.models import BusinessSession

SESSION_COOKIE = 'hx_overseas_session'
COOKIE_PATH = '/api/overseas/v1'


def issue_session(session, user_id, identity_session_id, expires_at):
    return issue(session, BusinessSession, user_id, get_settings().auth_session_ttl_seconds,
                 identity_session_id=identity_session_id, expires_at=expires_at)


def resolve_session(session, token):
    return resolve(session, BusinessSession, token)


def revoke_session(session, token):
    return revoke(session, BusinessSession, token)
