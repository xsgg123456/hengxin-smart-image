from uuid import UUID

import pytest
from sqlalchemy import event, select

from app.membership import service
from app.membership.schemas import Decision
from membership_helpers import (membership_env, files_env, overseas, post, decide,
                                seed_applicant, db_snapshot, HEADERS)


@pytest.mark.parametrize('registered', [False, True])
def test_access_is_read_only_even_with_changed_profile_and_old_session(membership_env, registered):
    env = membership_env
    if registered:
        seed_applicant(env)
    env['assertion']['member']['name'] = '更新姓名不得写入'
    before = db_snapshot(env)

    def no_write(conn, cursor, statement, parameters, context, executemany):
        assert statement.lstrip().split()[0].upper() not in ('INSERT', 'UPDATE', 'DELETE')

    engine = env['factory'].kw['bind']
    event.listen(engine, 'before_cursor_execute', no_write)
    try:
        for _ in range(2):
            response = post(env, 'access')
            assert response.status_code == 200
            assert response.json()['state'] == ('allowed' if registered else 'unregistered')
            assert 'set-cookie' not in response.headers
            if registered:
                assert response.json()['member']['name'] == '同名员工'
                assert response.json()['member']['identitySessionId'] == 'applicant-session'
    finally:
        event.remove(engine, 'before_cursor_execute', no_write)
    assert db_snapshot(env) == before


def test_unknown_session_never_creates_member_application_or_new_session(membership_env):
    env = membership_env
    before = db_snapshot(env)
    assert post(env, 'session').status_code == 403
    with env['factory']() as session:
        assert session.scalar(select(env['adapter'].Application)) is None
        assert len(list(session.scalars(select(env['members'])))) == 1
        if env['business'] == 'overseas':
            assert session.scalar(select(env['sessions'])).revoked_at is not None
        else:
            assert session.scalar(select(env['sessions'])) is None
    # Other than the documented old-session revocation, no business state changed.
    after = db_snapshot(env)
    after.pop(env['sessions'].__tablename__)
    before.pop(env['sessions'].__tablename__)
    assert before == after


def test_application_duplicate_and_withdraw_preserve_event_history(membership_env):
    env = membership_env
    application = post(env, 'application').json()
    assert application['status'] == 'pending' and application['version'] == 1
    assert post(env, 'application').json() == application
    assert post(env, 'access').json()['state'] == 'pending'
    with env['factory']() as session:
        assert len(list(session.scalars(select(env['members'])))) == 1
        assert len(list(session.scalars(select(env['adapter'].Event)))) == 1
    withdrawn = post(env, 'application/withdraw').json()
    assert withdrawn['status'] == 'withdrawn' and withdrawn['version'] == 2
    assert post(env, 'application/withdraw').json() == withdrawn
    assert post(env, 'access').json()['state'] == 'unregistered'
    reopened = post(env, 'application').json()
    assert reopened['id'] == application['id'] and reopened['version'] == 3
    with env['factory']() as session:
        assert [row.action for row in session.scalars(select(env['adapter'].Event).order_by(
            env['adapter'].Event.created_at))] == ['submit', 'withdraw', 'submit']


def test_reject_reapply_approve_and_list_all_statuses(membership_env):
    env = membership_env
    application = post(env, 'application').json()
    rejected = decide(env, application, decision='reject', role=None, reason='资料待确认')
    assert rejected.status_code == 200
    assert rejected.json()['reason'] == '资料待确认'
    assert post(env, 'access').json()['state'] == 'rejected'
    assert post(env, 'application/withdraw').status_code == 409
    listing = env['client'].get(env['management'] + '/applications').json()
    assert listing['total'] == 1 and listing['items'][0]['status'] == 'rejected'
    assert env['client'].get(env['management'] + '/applications?status=pending').json()['total'] == 0
    reopened = post(env, 'application').json()
    assert reopened['version'] == 3
    assert decide(env, reopened, version=1).status_code == 409
    assert decide(env, reopened, role='not-a-role').status_code == 422
    approved = decide(env, reopened)
    assert approved.status_code == 200 and approved.json()['status'] == 'approved'
    assert decide(env, reopened).status_code == 409
    assert post(env, 'application/withdraw').status_code == 409
    assert post(env, 'application').status_code == 409
    assert post(env, 'access').json()['state'] == 'allowed'
    assert post(env, 'session').json()['identitySessionId'] == 'applicant-session'
    # Domestic unit fixture overrides session resolution for the administrator; actual /me tested separately.
    if env['business'] == 'overseas':
        assert env['client'].get(env['base'] + '/auth/me').json()['identitySessionId'] == 'applicant-session'
    with env['factory']() as session:
        assert len(list(session.scalars(select(env['members'])))) == 2


def test_legacy_hidden_and_ordinary_edit_cannot_bypass_application(membership_env):
    env = membership_env
    target = seed_applicant(env, 'pending', 'legacy_unconfirmed', role=None)
    assert post(env, 'access').json()['state'] == 'legacy_unconfirmed'
    default = env['client'].get(env['management']).json()
    legacy = env['client'].get(env['management'] + '?directory=legacy').json()
    assert default['total'] == 1 and legacy['total'] == 1
    assert legacy['items'][0]['id'] == str(target)
    if env['business'] == 'domestic':
        result = env['client'].put(env['management'] + '/' + str(target),
            json={'id': str(target), 'status': 'active', 'role': 'designer'})
    else:
        result = env['client'].patch(env['management'] + '/' + str(target), headers=HEADERS,
            json={'status': 'active', 'roles': ['designer'], 'version': 1})
    assert result.status_code == 409
    application = post(env, 'application').json()
    assert decide(env, application).status_code == 200
    assert env['client'].get(env['management'] + '?directory=legacy').json()['total'] == 0
    assert env['client'].get(env['management']).json()['total'] == 2
    with env['factory']() as session:
        assert session.get(env['members'], target).directory_state == 'enrolled'
        assert len(list(session.scalars(select(env['members'])))) == 2


@pytest.mark.parametrize('status,role', [('disabled', 'designer'), ('active', None), ('pending', None)])
def test_enrolled_disabled_or_revoked_member_cannot_self_reapply(membership_env, status, role):
    env = membership_env
    seed_applicant(env, status=status, role=role)
    before = db_snapshot(env)
    assert post(env, 'access').json()['state'] == 'disabled'
    assert post(env, 'application').status_code == 403
    assert db_snapshot(env) == before


def test_identity_only_inputs_and_missing_browser_proof_are_rejected(membership_env):
    env = membership_env
    assert post(env, 'application', name='伪造', role='super_admin').status_code == 422
    response = env['client'].post(env['base'] + '/auth/identity/application', json={'ticket': 't'})
    assert response.status_code == 403
    assert post(env, 'application/withdraw').status_code == 404
    application = post(env, 'application').json()
    env['assertion']['member']['provider_user_id'] = 'different-person'
    assert post(env, 'application/withdraw').status_code == 404
    assert post(env, 'access').json()['state'] == 'unregistered'
    with env['factory']() as session:
        assert session.get(env['adapter'].Application, UUID(application['id'])).status == 'pending'


def test_approval_reauthorizes_actor_and_audit_failure_rolls_back(membership_env, monkeypatch):
    env = membership_env
    application = post(env, 'application').json()
    adapter = env['adapter']
    before = db_snapshot(env)

    def fail(mapper, connection, target):
        if target.action == 'approve':
            raise RuntimeError('audit unavailable')

    event.listen(adapter.Event, 'before_insert', fail)
    try:
        with env['factory']() as session:
            actor = session.get(env['members'], env['actor_id'])
            with pytest.raises(RuntimeError, match='audit unavailable'):
                service.decide(session, adapter, actor, UUID(application['id']),
                               Decision(decision='approve', role='designer', version=1))
    finally:
        event.remove(adapter.Event, 'before_insert', fail)
    assert db_snapshot(env) == before
    with env['factory']() as session:
        actor = session.get(env['members'], env['actor_id'])
        with env['factory'].begin() as other:
            other.get(env['members'], env['actor_id']).status = 'disabled'
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as error:
            service.decide(session, adapter, actor, UUID(application['id']),
                           Decision(decision='approve', role='designer', version=1))
        assert error.value.status_code == 403


def test_legacy_session_and_legacy_login_cannot_use_existing_role(membership_env):
    env = membership_env
    from datetime import timedelta
    from app.db.timestamps import utcnow
    target = seed_applicant(env, directory='legacy_unconfirmed')
    with env['factory'].begin() as session:
        if env['business'] == 'domestic':
            from app.main import app
            from app.modules.auth.dependencies import get_identity_id
            from app.modules.auth.sessions import issue_session, SESSION_COOKIE
            app.dependency_overrides.pop(get_identity_id)
            token = issue_session(session, target)
        else:
            from app.overseas.auth.sessions import issue_session, SESSION_COOKIE
            token = issue_session(session, target, 'legacy-session', utcnow() + timedelta(hours=1))
    env['client'].cookies.clear()
    env['client'].cookies.set(SESSION_COOKIE, token)
    assert env['client'].get(env['base'] + '/auth/me').status_code == 403
    assert post(env, 'session').status_code == 403
    assert post(env, 'access').json()['state'] == 'legacy_unconfirmed'


def test_application_name_search_matches_total_and_escapes_wildcards(membership_env):
    env = membership_env
    env['assertion']['member']['name'] = 'Alice_%'
    first = post(env, 'application').json()
    env['assertion']['member'].update(provider_user_id='second-applicant', name='Bob')
    post(env, 'application')
    base = env['management'] + '/applications'
    assert env['client'].get(base).json()['total'] == 2
    for search in ('alice', '%', '_'):
        result = env['client'].get(base, params={'search': search, 'pageSize': 1}).json()
        assert result['total'] == 1 and result['items'][0]['id'] == first['id']
    assert env['client'].get(base, params={'search': 'missing'}).json()['total'] == 0
    assert env['client'].get(base, params={'search': 'x' * 101}).status_code == 422


def test_rejection_reason_required_trimmed_and_limited(membership_env):
    env = membership_env
    application = post(env, 'application').json()
    for reason in (None, '', '  ', 'x' * 1001):
        assert decide(env, application, decision='reject', role=None, reason=reason).status_code == 422
    result = decide(env, application, decision='reject', role=None, reason='  ' + '原' * 995 + '  ')
    assert result.status_code == 200 and result.json()['reason'] == '原' * 995
