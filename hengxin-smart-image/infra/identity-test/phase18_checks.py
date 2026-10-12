"""Phase18 assertions over real HTTP; no business endpoint substitutions."""
import httpx
from sqlalchemy import text

from phase18_fixtures import ROLES

EXPECTED = {
    'operator': {'task.read', 'stats.read', 'task.create'},
    'operator_manager': {'task.read', 'stats.read', 'task.create'},
    'designer': {'task.read', 'stats.read', 'task.design'},
    'design_manager': {'task.read', 'stats.read', 'task.design', 'task.reassign'},
    'super_admin': {'task.read', 'stats.read', 'task.reassign', 'members.manage',
                    'skills.manage', 'settings.manage'},
}


def run(h, ids):
    base = h.BUSINESS['overseas'][0] + '/api/overseas/v1/members'
    target = base + '/' + ids['p18-target']
    for code, role in [(f'p18-{r}', r) for r in ROLES] + [('p18-admin', 'super_admin')]:
        with h.login(code) as client:
            response = h.exchange(client, 'overseas').json()
            current = h.me(client, 'overseas').json()
            assert set(current['capabilities']) == EXPECTED[role], current
            assert set(response['capabilities']) == EXPECTED[role], response
            if role != 'super_admin':
                for url in (base, target, target + '/audit'):
                    h.expect(client.get(url), 403)
                h.expect(client.patch(target, json={
                    'roles': ['super_admin'], 'status': 'active', 'version': 1}), 403)
    print('PASS five role capabilities and four non-admin API guards', flush=True)
    with h.login('p18-admin') as admin:
        h.exchange(admin, 'overseas')
        def detail(url=target):
            return h.expect(admin.get(url), 200).json()
        def patch(member, roles, status='active', expected=200):
            return h.expect(admin.patch(base + '/' + member['id'], json={
                'roles': roles, 'status': status, 'version': member['version']}), expected)
        first = h.expect(admin.get(base, params={'pageSize': 2}), 200).json()
        second = h.expect(admin.get(base, params={'pageSize': 2, 'page': 2}), 200).json()
        assert len(first['items']) == len(second['items']) == 2 and first['total'] >= len(ids)
        assert first['pageSize'] == 2 and second['page'] == 2
        assert not {m['id'] for m in first['items']} & {m['id'] for m in second['items']}
        for params in ({'search': 'p18-target'}, {'search': '测试部门'}, {'status': 'pending'},
                       {'role': 'super_admin'}, {'search': 'no-such-member'}):
            result = h.expect(admin.get(base, params=params), 200).json()
            for row in result['items']:
                if 'status' in params:
                    assert row['status'] == params['status']
                if 'role' in params:
                    assert params['role'] in row['roles']
                if 'search' in params:
                    assert params['search'] in row['name'] or params['search'] in row['department']
            if params == {'search': 'p18-target'}:
                assert result['total'] == 1
            if params == {'search': 'no-such-member'}:
                assert result['total'] == 0
        for params in ({'pageSize': 101}, {'page': 0}, {'role': 'unknown'}, {'search': 'x' * 101}):
            h.expect(admin.get(base, params=params), 422)
        h.expect(admin.get(base + '/00000000-0000-0000-0000-000000000000'), 404)
        before = detail()
        updated = patch(before, ['operator', 'designer', 'operator']).json()
        assert set(updated['roles']) == {'operator', 'designer'} and updated['version'] == before['version'] + 1
        patch(before, ['super_admin'], expected=409)
        assert detail() == updated
        for body in ({'roles': [], 'status': 'active', 'version': updated['version']},
                     {'roles': ['unknown'], 'status': 'active', 'version': updated['version']},
                     {'roles': ['operator'], 'status': 'active', 'version': updated['version'], 'name': 'tamper'}):
            h.expect(admin.patch(target, json=body), 422)
        h.expect(admin.patch(target, json={'roles': ['operator'], 'status': 'active',
            'version': updated['version']}, headers={'Origin': 'https://evil.invalid'}), 403)
        with h.login('p18-target') as member:
            h.exchange(member, 'overseas')
            assert set(h.me(member, 'overseas').json()['capabilities']) == EXPECTED['operator'] | EXPECTED['designer']
            patch(detail(), ['super_admin'])
            h.expect(member.get(base), 200)
            patch(detail(), ['operator'])
            h.expect(member.get(base), 403)
            assert set(h.me(member, 'overseas').json()['capabilities']) == EXPECTED['operator']
            patch(detail(), ['operator'], 'disabled')
            h.me(member, 'overseas', 401)
        audit = h.expect(admin.get(target + '/audit'), 200).json()['items']
        assert len(audit) == 4, audit
        assert audit[0]['after']['status'] == 'disabled'
        for entry in audit:
            assert entry['actorId'] == ids['p18-admin']
            assert set(entry['before']) == set(entry['after']) == {'roles', 'status', 'version'}
        with h.ENGINES['overseas'].connect() as connection:
            assert connection.execute(text('SELECT count(*) FROM overseas_member_audits WHERE member_id=:id'),
                                      {'id': ids['p18-target']}).scalar_one() == len(audit)
        with h.login('p18-admin2') as fresh:
            h.exchange(fresh, 'overseas')
            assert h.expect(fresh.get(target + '/audit'), 200).json()['items'] == audit
        print('PASS pagination filters activation multi-role stale409 immediate revocation disable audit persistence', flush=True)
        admin2_url = base + '/' + ids['p18-admin2']
        patch(detail(admin2_url), ['operator'])
        own = detail(base + '/' + ids['p18-admin'])
        patch(own, ['operator'], expected=409)
        patch(own, ['super_admin'], 'disabled', 409)
        patch(detail(admin2_url), ['super_admin'])
        with h.login('p18-dual') as dual:
            for kind in h.BUSINESS:
                h.exchange(dual, kind)
            domestic = h.me(dual, 'domestic').json()
            assert domestic['role'] == 'super_admin'
            h.expect(dual.get(base), 403)
            token = dual.cookies.get('hx_session')
            for name in ('hx_session', 'hx_overseas_session'):
                with httpx.Client(headers={'Cookie': name + '=' + token}) as isolated:
                    h.expect(isolated.get(base), 401)
            dual_url = base + '/' + ids['p18-dual']
            patch(detail(dual_url), ['designer'])
            assert h.me(dual, 'domestic').json() == domestic
            patch(detail(dual_url), ['designer'], 'disabled')
            h.me(dual, 'overseas', 401)
            assert h.me(dual, 'domestic').json() == domestic
            patch(detail(dual_url), ['operator'])
        print('PASS last-admin409 domestic admin cookie isolation and domestic session unchanged', flush=True)
    print('READY Phase18 codes: p18-admin p18-admin2 p18-pending p18-dual and p18-<role>', flush=True)
