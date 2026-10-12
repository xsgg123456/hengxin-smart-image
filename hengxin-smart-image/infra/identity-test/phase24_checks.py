"""Management persistence, scoped facts, immutable skills and runtime configuration."""
from contextlib import ExitStack
import os
from uuid import UUID, uuid4
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker
from app.core.config import get_settings
from app.overseas.execution import claims, runner
from app.overseas.execution.models import Job
from local_cli_fixture import configured_runner
from phase19_fixtures import domestic_snapshot


def run(h):
    previous = os.environ.copy()
    os.environ.update(h.environment('overseas'))
    get_settings.cache_clear()
    settings = get_settings()
    factory = sessionmaker(h.ENGINES['overseas'], expire_on_commit=False)
    before = domestic_snapshot(h)
    base = h.BUSINESS['overseas'][0] + '/api/overseas/v1'
    root = base + '/management'
    try:
        with ExitStack() as stack:
            clients = []
            for code in ('p18-operator', 'p18-designer', 'p19-designer2', 'p18-admin', 'p18-design_manager', 'p18-operator_manager'):
                client = stack.enter_context(h.login(code))
                h.exchange(client, 'overseas')
                clients.append(client)
            operator, designer, stranger, admin, manager, operator_manager = clients

            def config():
                return h.expect(admin.get(root + '/settings'), 200).json()

            def patch_config(**changes):
                current = config()
                body = {k: v for k, v in current.items() if k != 'autoCleanup'}
                body.update(changes)
                return h.expect(admin.patch(root + '/settings', json=body), 200).json()

            initial = config()
            for client in (operator, designer, manager, operator_manager):
                h.expect(client.get(root + '/settings'), 403)
                h.expect(client.get(root + '/skills'), 403)
                h.expect(client.get(root + '/usage'), 200)
                h.expect(client.get(root + '/jobs'), 200)
            bad = {k: v for k, v in initial.items() if k != 'autoCleanup'}
            h.expect(admin.patch(root + '/settings', json={**bad, 'concurrency': 6}), 422)
            h.expect(admin.patch(root + '/settings', json={**bad, 'autoCleanup': True}), 422)
            body = {'name': 'phase24-layout', 'stage': 'analysis', 'files': {'SKILL.md': '# Layout v1\nCreate the complete frozen SKU plan.'}}
            skill = h.expect(admin.post(root + '/skills', json=body), 201).json()
            h.expect(admin.post(root + '/skills', json={**body, 'name': 'bad-path', 'files': {'../SKILL.md': 'bad'}}), 422)
            h.expect(admin.post(root + '/skills', json=body), 409)
            configured = patch_config(concurrency=2, timeoutSeconds=120,
                defaults={**initial['defaults'], 'analysis': skill['id']})
            h.expect(admin.patch(root + '/settings', json=bad), 409)
            uid = h.expect(designer.get(base + '/auth/me'), 200).json()['id']

            def create(suffix, blocked=False):
                material = h.expect(operator.post(base + '/materials', params={'kind': 'competitor'},
                    files={'file': ('input.csv', b'item,value\nproduct,charger\n', 'text/csv')}), 201).json()
                response = operator.post(base + '/tasks', headers={'Idempotency-Key': str(uuid4())},
                    json=dict(name='Phase24管理验证' + suffix, productName='Charger24', brand='HX24',
                        platform='Amazon', market='US', remarks='', skus=[{'code': 'P24'}],
                        designerId=uid, materialIds=[material['id']]))
                if blocked:
                    assert response.status_code in (409, 422), response.text
                    return None
                return h.expect(response, 201).json()

            def job(task):
                with factory() as session:
                    return session.scalar(select(Job).where(Job.task_id == UUID(task['id'])))

            first = create('旧快照')
            old = job(first)
            assert old.payload['skill']['files'] == body['files']
            assert old.payload['runtime']['timeoutSeconds'] == 120
            version2 = h.expect(admin.post(root + '/skills/' + skill['id'] + '/versions',
                json={'version': skill['version'], 'files': {'SKILL.md': '# Layout v2\nImproved frozen plan.'}}), 200).json()
            assert version2['currentVersion'] == 2 and len(version2['versions']) == 2
            h.expect(admin.post(root + '/skills/' + skill['id'] + '/versions',
                json={'version': skill['version'], 'files': body['files']}), 409)
            patch_config(timeoutSeconds=180, paused=True)
            second = create('新快照')
            new = job(second)
            assert new.payload['runtime']['timeoutSeconds'] == 180
            assert new.payload['skill']['version'] == 2
            assert job(first).payload == old.payload
            assert claims.claim(factory, new.id) is None
            patch_config(paused=False)
            plan = {'skus': [{'code': 'P24', 'pictures': [{'title': '主图', 'description': '完整展示',
                'prompt': 'A clear product image.', 'width': 32, 'height': 32}]}]}
            with configured_runner(settings, plan, usage={'input_tokens': 10, 'output_tokens': 20}):
                runner.run(factory, old.id)
                runner.run(factory, new.id)
            usage = h.expect(operator.get(root + '/usage', params={'taskId': first['id']}), 200).json()
            assert usage['jobs'] == usage['succeeded'] == 1
            assert usage['inputTokens'] == 10 and usage['outputTokens'] == 20 and usage['cost'] is None
            hidden = h.expect(stranger.get(root + '/jobs', params={'taskId': first['id']}), 200).json()
            assert hidden['items'] == [] and hidden['total'] == 0
            visible = h.expect(manager.get(root + '/jobs', params={'taskId': first['id'], 'pageSize': 1}), 200).json()
            assert visible['total'] == 1 and visible['items'][0]['taskId'] == first['id']
            assert not any(k in str(visible) for k in ('auth_file', 'object_key', 'checksum', 'Create the complete'))
            disabled = h.expect(admin.patch(root + '/skills/' + skill['id'],
                json={'version': version2['version'], 'enabled': False}), 200).json()
            assert not disabled['enabled']
            create('停用默认不可提交', blocked=True)
            # Existing completed snapshots stay readable when a current binding is disabled.
            assert job(first).status == 'succeeded' and job(first).payload == old.payload
            h.expect(admin.patch(root + '/skills/' + skill['id'],
                json={'version': disabled['version'], 'enabled': True}), 200)
            # Restart the API only: sessions and all management state must survive.
            h.PROCESSES['overseas'].terminate()
            h.PROCESSES['overseas'].wait(timeout=10)
            h.start('overseas', 'app.overseas.main:app', 8009, h.environment('overseas'))
            after_restart = config()
            assert after_restart['timeoutSeconds'] == 180 and after_restart['defaults']['analysis'] == skill['id']
            stored = h.expect(admin.get(root + '/skills'), 200).json()['items']
            assert next(s for s in stored if s['id'] == skill['id'])['currentVersion'] == 2
            patch_config(paused=initial['paused'], concurrency=initial['concurrency'],
                timeoutSeconds=initial['timeoutSeconds'], defaults=initial['defaults'])
            assert domestic_snapshot(h) == before
            print('PASS management real HTTP: scoped accounting, parsed usage, immutable skill versions, runtime freeze, pause admission, stale conflicts and API restart persistence', flush=True)
    finally:
        os.environ.clear()
        os.environ.update(previous)
        get_settings.cache_clear()
