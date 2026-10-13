"""Extra identities enter through the same registration and administrator API."""
from sqlalchemy import text

CODES = ('p19-operator2', 'p19-designer2')


def grant(h, admin, member_id, roles, status='active'):
    url = h.BUSINESS['overseas'][0] + '/api/overseas/v1/members/' + member_id
    member = h.expect(admin.get(url), 200).json()
    return h.expect(admin.patch(url, json={
        'roles': roles, 'status': status, 'version': member['version']}), 200).json()


def prepare(h, ids):
    ids = dict(ids)
    applications = {}
    for code in CODES:
        with h.login(code) as client:
            h.exchange(client, 'overseas', status=403)
            applications[code] = h.expect(client.post(
                h.BUSINESS['overseas'][0] + '/api/overseas/v1/auth/identity/application',
                json={'ticket': h.ticket(client, 'overseas', 'application')}), 200).json()
    with h.login('p18-admin') as admin:
        h.exchange(admin, 'overseas')
        for code, role in zip(CODES, ('operator', 'designer')):
            application = applications[code]
            h.expect(admin.post(h.BUSINESS['overseas'][0] + '/api/overseas/v1/members/applications/'
                + application['id'] + '/decision', json={
                    'decision': 'approve', 'role': role, 'version': application['version']}), 200)
    with h.ENGINES['overseas'].connect() as connection:
        for row in connection.execute(text(
                "SELECT id,provider_user_id FROM overseas_members WHERE provider_user_id LIKE 'p19-%'")):
            ids[row.provider_user_id] = str(row.id)
    return ids


def domestic_snapshot(h):
    """Compare every domestic public table including its complete row contents."""
    with h.ENGINES['domestic'].connect() as connection:
        tables = connection.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")).scalars().all()
        return {name: connection.execute(text(
            'SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text), '\
            "'[]'::jsonb) FROM " + connection.dialect.identifier_preparer.quote(name) + ' t')).scalar_one()
            for name in tables}
