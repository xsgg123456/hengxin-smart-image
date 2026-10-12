"""Domestic wrappers around shared server-side session primitives."""
from app.core.config import get_settings
from app.identity.tokens import hash_token as hash_session_token
from app.identity.session_records import issue, resolve, revoke
from app.modules.auth.models import AuthSessionRecord

SESSION_COOKIE = 'hx_session'


def issue_session(session, user_id, now=None):
    return issue(session, AuthSessionRecord, user_id,
                 get_settings().auth_session_ttl_seconds, now=now)


def resolve_session(session, token, now=None):
    return resolve(session, AuthSessionRecord, token, now)


def revoke_session(session, token, now=None):
    return revoke(session, AuthSessionRecord, token, now)
