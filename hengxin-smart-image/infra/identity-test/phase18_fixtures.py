"""Only disposable fixtures; bootstrap and grants go through production paths."""
import subprocess
from uuid import uuid4

from sqlalchemy import text

ROLES = ('operator', 'operator_manager', 'designer', 'design_manager')
CODES = tuple('p18-' + role for role in ROLES) + (
    'p18-admin', 'p18-admin2', 'p18-pending', 'p18-dual', 'p18-target')


def bootstrap(h, users='p18-admin,p18-admin2', success=True):
    env = h.environment('overseas')
    env.update(OVERSEAS_BOOTSTRAP_ADMIN_CORP_ID='test-corp',
               OVERSEAS_BOOTSTRAP_ADMIN_USER_IDS=users)
    result = subprocess.run([h.PYTHON, '-m', 'app.overseas.members.bootstrap'],
                            env=env, capture_output=True, text=True)
    assert (result.returncode == 0) == success, result.stdout + result.stderr
    return result.stdout


def prepare(h):
    # Unregistered bootstrap identities are forbidden.
    bootstrap(h, success=False)
    for code in CODES:
        with h.login(code) as client:
            h.exchange(client, 'overseas', status=403)
    with h.ENGINES['overseas'].connect() as connection:
        rows = connection.execute(text(
            "SELECT id,provider_user_id,status FROM overseas_members WHERE provider_user_id LIKE 'p18-%'"))
        fixtures = {row.provider_user_id: str(row.id) for row in rows if row.status == 'pending'}
    assert len(fixtures) == len(CODES), fixtures
    bootstrap(h)
    assert '0 ' in bootstrap(h), 'Bootstrap must be idempotent'
    bootstrap(h, users='p18-target', success=False)
    base = h.BUSINESS['overseas'][0] + '/api/overseas/v1/members/'
    with h.login('p18-admin') as admin:
        h.exchange(admin, 'overseas')
        for code in (*('p18-' + role for role in ROLES), 'p18-dual'):
            member = h.expect(admin.get(base + fixtures[code]), 200).json()
            role = code.removeprefix('p18-') if code != 'p18-dual' else 'operator'
            h.expect(admin.patch(base + member['id'], json={
                'roles': [role], 'status': 'active', 'version': member['version']}), 200)
    # Domestic admin fixture uses only the disposable domestic database.
    with h.ENGINES['domestic'].begin() as connection:
        uid = str(uuid4())
        connection.execute(text("INSERT INTO users (id,name,role,status,identity_source,created_at,updated_at) "
            "VALUES (:id,'p18-dual','super_admin','active','dingtalk',now(),now())"), {'id': uid})
        connection.execute(text("INSERT INTO user_identities "
            "(id,user_id,provider,corp_id,provider_user_id,union_id,department,created_at,updated_at) "
            "VALUES (:id,:uid,'dingtalk','test-corp','p18-dual','p18-dual','test',now(),now())"),
            {'id': str(uuid4()), 'uid': uid})
    print('PASS explicit bootstrap pending identities and idempotency', flush=True)
    return fixtures
