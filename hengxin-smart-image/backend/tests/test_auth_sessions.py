from datetime import timedelta
from uuid import uuid4

from app.models import utcnow
from app.modules.auth.models import RoleAssignmentRecord, UserIdentityRecord
from app.modules.auth.sessions import SESSION_COOKIE, issue_session
from app.modules.auth.dependencies import get_identity_id
from app.main import app
from app.resource_models import UserRecord
from files_helpers import files_env


def test_server_session_cookie_authenticates_and_logout_revokes(files_env):
    client, factory, _, identity = files_env
    with factory.begin() as session:
        token = issue_session(session, identity[0])
    app.dependency_overrides.pop(get_identity_id)
    response = client.get('/api/v1/auth/me', cookies={SESSION_COOKIE: token})
    assert response.status_code == 200
    assert client.post('/api/v1/auth/logout', cookies={SESSION_COOKIE: token}).status_code == 204
    assert client.get('/api/v1/auth/me', cookies={SESSION_COOKIE: token}).status_code == 401


def test_expired_session_is_rejected(files_env):
    client, factory, _, identity = files_env
    with factory.begin() as session:
        token = issue_session(session, identity[0], now=utcnow() - timedelta(hours=9))
    app.dependency_overrides.pop(get_identity_id)
    assert client.get('/api/v1/auth/me', cookies={SESSION_COOKIE: token}).status_code == 401


def test_super_admin_can_list_filter_and_update_members(files_env):
    client, factory, _, identity = files_env
    with factory.begin() as session:
        actor = session.get(UserRecord, identity[0])
        actor.role = 'super_admin'
        pending = UserRecord(id=uuid4(), name='待授权成员', role=None, status='pending', identity_source='dingtalk')
        session.add(pending)
        session.add(UserIdentityRecord(
            user_id=pending.id, provider='dingtalk', corp_id='corp',
            provider_user_id='member-1', department='设计部',
        ))
    page = client.get('/api/v1/management/users?search=设计部&pageSize=1').json()
    assert page['total'] == 1 and page['items'][0]['name'] == '待授权成员'
    updated = client.put('/api/v1/management/users/' + str(pending.id), json={
        'id': str(pending.id), 'role': 'designer', 'status': 'active',
    })
    assert updated.status_code == 200
    assert updated.json()['role'] == 'designer'
    with factory() as session:
        member = session.get(UserRecord, pending.id)
        assignment = session.query(RoleAssignmentRecord).filter_by(user_id=pending.id).one()
        assert (member.role, member.status, assignment.role, assignment.assigned_by) == (
            'designer', 'active', 'designer', identity[0],
        )


def test_non_admin_cannot_manage_members_and_last_admin_is_protected(files_env):
    client, factory, _, identity = files_env
    with factory.begin() as session:
        actor = session.get(UserRecord, identity[0])
        actor.role = 'operator'
        target = UserRecord(id=uuid4(), name='成员', role='designer', status='active', identity_source='dingtalk')
        session.add(target)
    assert client.get('/api/v1/management/users').status_code == 403
    assert client.put('/api/v1/management/users/' + str(target.id), json={
        'id': str(target.id), 'role': 'operator', 'status': 'active',
    }).status_code == 403

    with factory.begin() as session:
        session.get(UserRecord, identity[0]).role = 'super_admin'
    response = client.put('/api/v1/management/users/' + str(identity[0]), json={
        'id': str(identity[0]), 'role': 'designer', 'status': 'active',
    })
    assert response.status_code == 409
