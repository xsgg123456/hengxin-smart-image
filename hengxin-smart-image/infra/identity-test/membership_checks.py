"""Membership isolation exercised over real HTTP and two disposable PostgreSQL DBs."""
from concurrent.futures import ThreadPoolExecutor
import subprocess
import signal
import time
from uuid import uuid4

from sqlalchemy import text

CODES = tuple('mi-' + suffix for suffix in (
    'domestic-admin', 'overseas-admin', 'apply-domestic', 'apply-overseas',
    'legacy', 'ui-applicant', 'ui-rejected', 'ui-other', 'ui-same-name',
))


def endpoints(h, kind):
    origin, auth = h.BUSINESS[kind]
    management = '/api/v1/management/users' if kind == 'domestic' else '/api/overseas/v1/members'
    return origin + auth + '/identity', origin + management


def operation(h, client, kind, action, purpose, status=200):
    auth, _ = endpoints(h, kind)
    return h.expect(client.post(auth + '/' + action,
        json={'ticket': h.ticket(client, kind, purpose)}), status).json()


def snapshot(h, kind):
    tables = (['users', 'user_identities', 'role_assignments', 'auth_sessions', 'domestic_member_audits']
              if kind == 'domestic' else ['overseas_members', 'overseas_member_roles', 'overseas_sessions',
                                         'overseas_member_audits'])
    tables += [kind + '_membership_applications', kind + '_membership_application_events']
    with h.ENGINES[kind].connect() as connection:
        return {table: sorted(str(tuple(row)) for row in connection.execute(text('SELECT * FROM ' + table)))
                for table in tables}


def seed_domestic_admin(h):
    uid = str(uuid4())
    with h.ENGINES['domestic'].begin() as connection:
        connection.execute(text("INSERT INTO users (id,name,role,status,identity_source,created_at,updated_at) "
            "VALUES (:id,'mi-domestic-admin','super_admin','active','dingtalk',now(),now())"), {'id': uid})
        connection.execute(text("INSERT INTO user_identities "
            "(id,user_id,provider,corp_id,provider_user_id,union_id,department,created_at,updated_at) "
            "VALUES (:id,:uid,'dingtalk','test-corp','mi-domestic-admin',NULL,'',now(),now())"),
            {'id': str(uuid4()), 'uid': uid})


def bootstrap_overseas(h):
    with h.login('mi-overseas-admin') as client:
        operation(h, client, 'overseas', 'application', 'application')
    env = h.environment('overseas')
    env.update(OVERSEAS_BOOTSTRAP_ADMIN_CORP_ID='test-corp',
               OVERSEAS_BOOTSTRAP_ADMIN_USER_IDS='mi-overseas-admin')
    for _ in range(2):
        result = subprocess.run([h.PYTHON, '-m', 'app.overseas.members.bootstrap'],
                                env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr


def check_readonly_and_selected_session(h):
    for code in ('both', 'domestic', 'overseas', 'neither'):
        before = {kind: snapshot(h, kind) for kind in h.BUSINESS}
        with h.login(code) as client:
            for _ in range(2):
                for kind in h.BUSINESS:
                    result = operation(h, client, kind, 'access', 'access')
                    assert result['state'] == ('allowed' if code in ('both', kind) else 'unregistered'), result
            assert before == {kind: snapshot(h, kind) for kind in h.BUSINESS}
            for kind in h.BUSINESS:
                h.me(client, kind, 401)
            if code != 'neither':
                selected = code if code != 'both' else 'domestic'
                other = 'overseas' if selected == 'domestic' else 'domestic'
                h.exchange(client, selected)
                assert snapshot(h, other) == before[other]
                identity = client.get(h.ID + h.PATH + '/me').json()
                assert h.me(client, selected).json()['identitySessionId'] == identity['sessionId']
    print('PASS both DBs unchanged by repeated access; only selected business creates sessions', flush=True)


def check_application(h, kind):
    other = 'overseas' if kind == 'domestic' else 'domestic'
    _, management = endpoints(h, kind)
    with h.login('mi-' + kind + '-admin') as admin, h.login('mi-apply-' + kind) as applicant:
        h.exchange(admin, kind)
        other_before = snapshot(h, other)
        total = h.expect(admin.get(management), 200).json()['total']
        first = operation(h, applicant, kind, 'application', 'application')
        again = operation(h, applicant, kind, 'application', 'application')
        assert first['id'] == again['id'] and first['version'] == again['version']
        assert operation(h, applicant, kind, 'access', 'access')['state'] == 'pending'
        assert h.expect(admin.get(management), 200).json()['total'] == total
        h.exchange(applicant, kind, status=403)
        withdrawn = operation(h, applicant, kind, 'application/withdraw', 'application')
        assert withdrawn['status'] == 'withdrawn'
        reopened = operation(h, applicant, kind, 'application', 'application')
        assert reopened['id'] == first['id'] and reopened['version'] > first['version']
        decision = management + '/applications/' + first['id'] + '/decision'
        rejected = h.expect(admin.post(decision, json={
            'decision': 'reject', 'version': reopened['version'], 'reason': 'wrong team'}), 200).json()
        assert rejected['status'] == 'rejected'
        assert operation(h, applicant, kind, 'access', 'access')['state'] == 'rejected'
        reopened = operation(h, applicant, kind, 'application', 'application')
        body = {'decision': 'approve', 'role': 'designer', 'version': reopened['version']}
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: admin.post(decision, json=body), range(2)))
        assert sorted(response.status_code for response in responses) == [200, 409], [r.text for r in responses]
        assert h.expect(admin.get(management), 200).json()['total'] == total + 1
        assert operation(h, applicant, kind, 'access', 'access')['state'] == 'allowed'
        member = h.exchange(applicant, kind).json()
        assert snapshot(h, other) == other_before
        # Fixture disable is restricted to this disposable DB; production auth must observe it.
        table = 'users' if kind == 'domestic' else 'overseas_members'
        with h.ENGINES[kind].begin() as connection:
            connection.execute(text('UPDATE ' + table + " SET status='disabled' WHERE id=:id"), {'id': member['id']})
        h.me(applicant, kind, 403)
        operation(h, applicant, kind, 'application', 'application', 403)
        assert operation(h, applicant, kind, 'access', 'access')['state'] == 'disabled'
        assert snapshot(h, other) == other_before
    print('PASS ' + kind + ' apply/withdraw/reject/reapply/concurrent approval/disabled and opposite DB unchanged', flush=True)


def seed_legacy(h, kind):
    uid = str(uuid4())
    with h.ENGINES[kind].begin() as connection:
        if kind == 'domestic':
            connection.execute(text("INSERT INTO users "
                "(id,name,role,status,directory_state,identity_source,created_at,updated_at) "
                "VALUES (:id,'mi-legacy',NULL,'pending','legacy_unconfirmed','dingtalk',now(),now())"), {'id': uid})
            connection.execute(text("INSERT INTO user_identities "
                "(id,user_id,provider,corp_id,provider_user_id,department,created_at,updated_at) "
                "VALUES (:id,:uid,'dingtalk','test-corp','mi-legacy','',now(),now())"),
                {'id': str(uuid4()), 'uid': uid})
        else:
            connection.execute(text("INSERT INTO overseas_members "
                "(id,corp_id,provider_user_id,name,department,status,directory_state,created_at,updated_at) "
                "VALUES (:id,'test-corp','mi-legacy','mi-legacy','','pending','legacy_unconfirmed',now(),now())"), {'id': uid})
    return uid


def check_legacy(h, kind):
    legacy_id = seed_legacy(h, kind)
    _, management = endpoints(h, kind)
    with h.login('mi-' + kind + '-admin') as admin, h.login('mi-legacy') as applicant:
        h.exchange(admin, kind)
        members = h.expect(admin.get(management, params={'pageSize': 100}), 200).json()
        assert legacy_id not in {row['id'] for row in members['items']}
        legacy = h.expect(admin.get(management, params={'directory': 'legacy'}), 200).json()
        assert legacy_id in {row['id'] for row in legacy['items']}
        assert operation(h, applicant, kind, 'access', 'access')['state'] == 'legacy_unconfirmed'
        h.exchange(applicant, kind, status=403)
        application = operation(h, applicant, kind, 'application', 'application')
        h.expect(admin.post(management + '/applications/' + application['id'] + '/decision',
            json={'decision': 'approve', 'role': 'operator', 'version': application['version']}), 200)
        assert h.exchange(applicant, kind).json()['id'] == legacy_id
        assert h.expect(admin.get(management), 200).json()['total'] == members['total'] + 1
        assert legacy_id not in {row['id'] for row in h.expect(admin.get(management,
            params={'directory': 'legacy'}), 200).json()['items']}
    print('PASS ' + kind + ' legacy excluded until explicit application/approval, stable member ID retained', flush=True)


def check_purpose_and_admin_boundaries(h):
    with h.login('mi-overseas-admin') as admin:
        h.exchange(admin, 'overseas')
        _, domestic = endpoints(h, 'domestic')
        h.expect(admin.get(domestic + '/applications'), 401)
        auth, _ = endpoints(h, 'overseas')
        value = h.ticket(admin, 'overseas', 'access')
        h.expect(admin.post(auth + '/application', json={'ticket': value}), 401)
        h.expect(admin.post(auth + '/session', json={'ticket': value}), 401)
        h.expect(admin.post(auth + '/access', json={'ticket': value}), 200)
    with h.login('mi-domestic-admin') as admin:
        h.exchange(admin, 'domestic')
        _, overseas = endpoints(h, 'overseas')
        h.expect(admin.get(overseas + '/applications'), 401)
    print('PASS independent admin roles and operation-bound tickets', flush=True)


def run(h):
    check_readonly_and_selected_session(h)
    seed_domestic_admin(h)
    bootstrap_overseas(h)
    for kind in h.BUSINESS:
        check_application(h, kind)
        check_legacy(h, kind)
    check_purpose_and_admin_boundaries(h)
    print('READY membership browser fixtures: mi-domestic-admin mi-overseas-admin mi-ui-applicant', flush=True)


def start_and_run(h, identity_env):
    h.start('identity', 'provider_app:app', 8010, identity_env)
    run(h)
    print('PASS ALL member isolation real HTTP integration', flush=True)


def serve(h, identity_env):
    if h.PROCESSES['identity'].poll() is not None:
        h.start('identity', 'provider_app:app', 8010, identity_env)

    def stop(signum, frame):
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop)
    print('READY browser fixture codes: both domestic overseas neither', flush=True)
    while True:
        time.sleep(1)
