"""Real task HTTP checks plus persistence and complete domestic isolation proof."""
from contextlib import ExitStack
from uuid import uuid4

from sqlalchemy import text

from phase19_fixtures import domestic_snapshot, grant, prepare


def run(h, fixtures):
    domestic_before = domestic_snapshot(h)
    ids = prepare(h, fixtures)
    base = h.BUSINESS['overseas'][0] + '/api/overseas/v1'
    with ExitStack() as stack:
        clients = {}
        for code in ('p18-admin', 'p18-operator', 'p18-operator_manager', 'p18-designer',
                     'p18-design_manager', 'p19-operator2', 'p19-designer2', 'p18-dual'):
            clients[code] = stack.enter_context(h.login(code))
            h.exchange(clients[code], 'overseas')
        admin, operator, designer = (clients[c] for c in ('p18-admin', 'p18-operator', 'p18-designer'))

        def get(client, path='/tasks', **params):
            return h.expect(client.get(base + path, params=params), 200).json()

        def create(client, payload, key, status=201):
            return h.expect(client.post(base + '/tasks', json=payload,
                                       headers={'Idempotency-Key': key}), status).json()

        body = {'name': 'Phase19 HTTP 首个图需', 'productName': '充电器', 'brand': 'HX',
                'platform': 'Amazon', 'market': '美国', 'remarks': '真实数据库验收',
                'skus': [{'code': 'SKU-19-A'}, {'code': 'SKU-19-B'}],
                'designerId': ids['p18-designer']}
        candidates = get(operator, '/task-designers', pageSize=1)
        second = get(operator, '/task-designers', pageSize=1, page=2)
        assert candidates['total'] == 3 and len(candidates['items']) == 1
        assert candidates['items'][0]['id'] != second['items'][0]['id']
        all_ids = {r['id'] for r in get(operator, '/task-designers')['items']}
        assert all_ids == {ids[c] for c in ('p18-designer', 'p18-design_manager', 'p19-designer2')}
        assert get(operator, '/task-designers', search='p19-designer2')['total'] == 1
        h.expect(designer.get(base + '/task-designers'), 403)
        grant(h, admin, ids['p19-designer2'], ['designer'], 'disabled')
        assert get(operator, '/task-designers', search='p19-designer2')['total'] == 0
        create(operator, {**body, 'designerId': ids['p19-designer2']}, 'disabled', 422)
        grant(h, admin, ids['p19-designer2'], ['designer'])
        h.exchange(clients['p19-designer2'], 'overseas')
        for patch in ({'name': ' '}, {'skus': [{'code': 'A'}, {'code': ' a '}]},
                      {'skus': []}, {'files': []}, {'designerId': ids['p18-admin']},
                      {'designerId': None}):
            create(operator, {**body, **patch}, str(uuid4()), 422)
        h.expect(operator.post(base + '/tasks', json=body), 422)
        for code in ('p18-designer', 'p18-design_manager', 'p18-admin'):
            create(clients[code], body, str(uuid4()), 403)
        first = create(operator, body, 'p19-create')
        assert first['status'] == 'created' and first['version'] == 1
        assert first['skus'] == body['skus'] and len(first['events']) == 1
        assert create(operator, body, 'p19-create', 200)['id'] == first['id']
        create(operator, {**body, 'name': '冲突内容'}, 'p19-create', 409)
        other = create(clients['p19-operator2'], {**body, 'name': '另一个运营的图需',
            'designerId': ids['p19-designer2'], 'skus': [{'code': 'ONLY-SECOND'}]}, 'p19-create')
        third = create(clients['p18-operator_manager'], {**body, 'name': '主管的图需'}, 'manager-create')
        expected = {'p18-operator': {first['id']}, 'p19-operator2': {other['id']},
                    'p18-designer': {first['id'], third['id']}, 'p19-designer2': {other['id']},
                    'p18-operator_manager': {first['id'], other['id'], third['id']},
                    'p18-design_manager': {first['id'], other['id'], third['id']},
                    'p18-admin': {first['id'], other['id'], third['id']}}
        for code, task_ids in expected.items():
            result = get(clients[code])
            assert result['total'] == len(task_ids) and {t['id'] for t in result['items']} == task_ids
        assert get(clients['p18-operator_manager'], scope='mine')['total'] == 1
        assert get(admin, scope='mine')['total'] == 0
        assert get(operator, search='ONLY-SECOND')['total'] == 0
        assert get(admin, search='ONLY-SECOND', pageSize=1)['items'][0]['id'] == other['id']
        assert get(operator, search=first['id'])['total'] == 1
        assert get(admin, status='created')['total'] == 3
        pages = [get(admin, page=p, pageSize=1) for p in (1, 2, 3, 4)]
        assert all(p['total'] == 3 for p in pages) and pages[3]['items'] == []
        assert {p['items'][0]['id'] for p in pages[:3]} == expected['p18-admin']
        for params in ({'page': 0}, {'pageSize': 101}, {'search': 'x' * 101}):
            h.expect(admin.get(base + '/tasks', params=params), 422)
        h.expect(operator.get(base + '/tasks/' + other['id']), 403)
        h.expect(admin.get(base + '/tasks/' + str(uuid4())), 404)
        print('PASS Phase19 candidates validation persistence five-role scope filtering pagination idempotency', flush=True)

        url = base + '/tasks/' + first['id'] + '/assignment'
        assignment = {'designerId': ids['p19-designer2'], 'version': 1}
        def assign(client, payload=assignment, key='p19-assign', status=200):
            return h.expect(client.patch(url, json=payload, headers={'Idempotency-Key': key}), status).json()
        for code in ('p18-operator', 'p18-designer', 'p18-operator_manager'):
            assign(clients[code], status=403)
        assign(admin, {'designerId': ids['p18-designer'], 'version': 1}, 'same', 409)
        changed = assign(clients['p18-design_manager'])
        assert changed['version'] == 2 and changed['designer']['id'] == ids['p19-designer2']
        assert changed['skus'] == first['skus'] and changed['status'] == 'created'
        assert len(changed['events']) == 2
        assert [e['version'] for e in changed['events']] == [1, 2]
        assert changed['events'][1]['beforeDesignerId'] == ids['p18-designer']
        assert changed['events'][1]['afterDesignerId'] == ids['p19-designer2']
        assert assign(clients['p18-design_manager'])['version'] == 2
        assign(admin, {'designerId': ids['p18-designer'], 'version': 1}, 'stale', 409)
        assign(clients['p18-design_manager'], {'designerId': ids['p18-designer'], 'version': 2},
               'p19-assign', 409)
        h.expect(designer.get(base + '/tasks/' + first['id']), 403)
        assert 'task.design' in get(clients['p19-designer2'], '/tasks/' + first['id'])['capabilities']
        assert create(operator, body, 'p19-create', 200)['version'] == 2
        grant(h, admin, ids['p19-designer2'], ['designer'], 'disabled')
        disabled = get(admin, '/tasks/' + first['id'])
        assert disabled['designer']['status'] == 'disabled' and not disabled['designer']['eligible']
        changed = assign(admin, {'designerId': ids['p18-designer'], 'version': 2}, 'resume')
        assert changed['version'] == 3 and len(changed['events']) == 3
        grant(h, admin, ids['p19-designer2'], ['designer'])
        grant(h, admin, ids['p18-dual'], ['operator', 'designer'])
        dual_body = {**body, 'designerId': ids['p18-dual'], 'name': '兼任本人创建'}
        dual = create(clients['p18-dual'], dual_body, 'dual-create')
        h.expect(admin.patch(base + '/tasks/' + dual['id'] + '/assignment', json={
            'designerId': ids['p18-designer'], 'version': 1}, headers={'Idempotency-Key': 'dual-move'}), 200)
        assert get(clients['p18-dual'], '/tasks/' + dual['id'])['capabilities'] == ['task.read']
        grant(h, admin, ids['p18-dual'], ['operator'])
        print('PASS Phase19 assignment old/new access stale409 current replay disabled recovery multi-role', flush=True)

    with h.login('p18-admin') as fresh:
        h.exchange(fresh, 'overseas')
        assert h.expect(fresh.get(base + '/tasks/' + first['id']), 200).json()['version'] == 3
    with h.ENGINES['overseas'].connect() as connection:
        counts = {table: connection.execute(text('SELECT count(*) FROM overseas_' + table)).scalar_one()
                  for table in ('tasks', 'task_skus', 'task_events', 'task_outbox', 'task_requests')}
        assert counts == {'tasks': 4, 'task_skus': 7, 'task_events': 7, 'task_outbox': 7, 'task_requests': 7}, counts
        assert connection.execute(text('SELECT count(*) FROM overseas_task_outbox WHERE published_at IS NOT NULL')).scalar_one() == 0
        assert connection.execute(text("SELECT to_regclass('jobs')")).scalar_one() is None
    assert domestic_snapshot(h) == domestic_before, 'Domestic tables or rows changed during Phase19'
    print('PASS Phase19 fresh-session persistence exact event/outbox/request counts and all domestic rows unchanged', flush=True)
    print('READY Phase19 extra browser codes: p19-operator2 p19-designer2', flush=True)
