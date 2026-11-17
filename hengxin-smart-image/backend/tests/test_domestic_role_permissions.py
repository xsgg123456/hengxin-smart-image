from sqlalchemy import select

from app.main import app
from app.modules.auth.dependencies import get_identity_id
from app.modules.auth.models import RoleAssignmentRecord
from app.modules.auth.sessions import SESSION_COOKIE, issue_session
from app.resource_models import UserRecord
from files_helpers import files_env
from membership_helpers import membership_env, overseas, post, decide


def test_retired_role_cannot_be_assigned_through_member_management(files_env):
    client, factory, _, identity = files_env
    with factory.begin() as session:
        session.get(UserRecord, identity[0]).role = 'super_admin'
        member = UserRecord(name='测试待分配', role='designer', status='active',
                            identity_source='dingtalk')
        session.add(member)
        session.flush()
        target = str(member.id)
    response = client.put('/api/v1/management/users/' + target,
        json={'id': target, 'role': 'design_manager', 'status': 'active'})
    assert response.status_code == 422
    with factory() as session:
        assert session.get(UserRecord, member.id).role == 'designer'
        assert session.scalar(select(RoleAssignmentRecord).where(
            RoleAssignmentRecord.user_id == member.id)) is None


def test_role_approval_is_domestic_only_and_overseas_manager_remains(membership_env):
    env = membership_env
    application = post(env, 'application').json()
    response = decide(env, application, role='design_manager')
    assert response.status_code == (422 if env['business'] == 'domestic' else 200)
    if env['business'] == 'domestic':
        with env['factory']() as session:
            record = session.scalar(select(env['adapter'].Application))
            assert record.status == 'pending'


def test_existing_cookie_observes_revoke_and_promotion_on_next_request(files_env):
    client, factory, _, identity = files_env
    with factory.begin() as session:
        session.get(UserRecord, identity[0]).role = 'super_admin'
        token = issue_session(session, identity[0])
    app.dependency_overrides.pop(get_identity_id)
    client.cookies.set(SESSION_COOKIE, token)
    assert client.get('/api/v1/management/users').status_code == 200
    with factory.begin() as session:
        session.get(UserRecord, identity[0]).role = 'design_manager'
    assert client.get('/api/v1/auth/me').status_code == 200
    for path in ['/management/users', '/management/activity', '/management/api-monitor',
                 '/management/retention/summary']:
        assert client.get('/api/v1' + path).status_code == 403, path
    with factory.begin() as session:
        session.get(UserRecord, identity[0]).role = 'designer'
    assert client.get('/api/v1/auth/me').json()['role'] == 'designer'
    assert client.get('/api/v1/management/users').status_code == 403
    with factory.begin() as session:
        session.get(UserRecord, identity[0]).role = 'super_admin'
    assert client.get('/api/v1/management/users').status_code == 200
