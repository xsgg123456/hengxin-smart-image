"""Real upload, API permissions and process-backed offline analysis protocol."""
from contextlib import ExitStack
import json
import os
from uuid import UUID, uuid4
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker
from app.core.config import get_settings
from app.overseas.execution import runner
from app.overseas.execution.models import Job
from local_cli_fixture import configured_runner
from phase19_fixtures import domestic_snapshot


def run(h):
    from app.overseas.plans.analysis import install
    install()
    previous = os.environ.copy()
    os.environ.update(h.environment('overseas'))
    get_settings.cache_clear()
    settings = get_settings()
    factory = sessionmaker(h.ENGINES['overseas'], expire_on_commit=False)
    before = domestic_snapshot(h)
    base = h.BUSINESS['overseas'][0] + '/api/overseas/v1'
    document = {'skus': [{'code': code, 'pictures': [{'title': '主图', 'description': '产品完整展示',
        'prompt': 'Create a clear product photograph.', 'width': 800, 'height': 800}]} for code in ('P22-A', 'P22-B')]}
    try:
        with ExitStack() as stack:
            clients = []
            for code in ('p18-operator', 'p18-designer', 'p19-designer2', 'p18-admin'):
                client = stack.enter_context(h.login(code))
                h.exchange(client, 'overseas')
                clients.append(client)
            operator, designer, stranger, admin = clients
            uid = h.expect(designer.get(base + '/auth/me'), 200).json()['id']
            material = h.expect(operator.post(base + '/materials', params={'kind': 'competitor'},
                files={'file': ('source.csv', b'item,value\nproduct,charger\n', 'text/csv')}), 201).json()
            body = dict(name='Phase22真实方案', productName='Charger', brand='HX', platform='Amazon',
                        market='US', remarks='', skus=[{'code': c} for c in ('P22-A', 'P22-B')],
                        designerId=uid, materialIds=[material['id']])
            task = h.expect(operator.post(base + '/tasks', headers={'Idempotency-Key': str(uuid4())}, json=body), 201).json()
            path = base + '/tasks/' + task['id']

            def detail():
                return h.expect(designer.get(path), 200).json()

            def plans():
                return h.expect(designer.get(path + '/plans'), 200).json()['items']

            assert task['status'] == 'analyzing'
            initial = plans()[0]
            assert initial['status'] == 'pending'
            h.expect(stranger.get(path + '/plans'), 403)
            h.expect(admin.post(path + '/analysis', headers={'Idempotency-Key': str(uuid4())},
                                json={'version': task['version'], 'feedback': '不可操作'}), 403)
            with configured_runner(settings, document) as fixture:
                runner.run(factory, initial['jobId'])
                ready = plans()[0]
                assert ready['status'] == 'ready' and ready['content'] == document
                assert detail()['status'] == 'plan'
                key = {'Idempotency-Key': str(uuid4())}
                modify = {'version': detail()['version'], 'feedback': '请调整各SKU排版'}
                h.expect(designer.post(path + '/analysis', json={**modify, 'feedback': ''}, headers=key), 422)
                h.expect(designer.post(path + '/analysis', json=modify, headers=key), 200)
                h.expect(designer.post(path + '/analysis', json=modify, headers=key), 200)
                assert len(plans()) == 2
                pending = plans()[0]
                confirm = path + '/plans/' + pending['id'] + '/confirm'
                h.expect(designer.post(confirm, headers={'Idempotency-Key': str(uuid4())},
                                      json={'version': detail()['version']}), 409)
                fixture.write_text(json.dumps({'skus': []}), encoding='utf-8')
                runner.run(factory, pending['jobId'])
                assert plans()[0]['status'] == 'failed' and detail()['status'] == 'analysisFailed'
                retry = {'version': detail()['version'], 'feedback': ''}
                h.expect(designer.post(path + '/analysis', json=retry, headers={'Idempotency-Key': str(uuid4())}), 200)
                fixture.write_text(json.dumps(document), encoding='utf-8')
                runner.run(factory, plans()[0]['jobId'])
                current = plans()[0]
                h.expect(designer.post(path + '/plans/' + initial['id'] + '/confirm',
                    json={'version': detail()['version']}, headers={'Idempotency-Key': str(uuid4())}), 409)
                version = detail()['version']
                key = {'Idempotency-Key': str(uuid4())}
                url = path + '/plans/' + current['id'] + '/confirm'
                result = h.expect(designer.post(url, json={'version': version}, headers=key), 200).json()
                assert result['status'] == 'generating'
                h.expect(designer.post(url, json={'version': version}, headers=key), 200)
                with factory() as session:
                    jobs = session.scalars(select(Job).where(Job.task_id == UUID(task['id']), Job.kind == 'generation')).all()
                    assert len(jobs) == 2 and all(job.status == 'queued' for job in jobs)
                assert plans()[0]['status'] == 'confirmed'
            assert domestic_snapshot(h) == before
            print('PASS plan real HTTP + offline child process: frozen inputs, full SKU protocol, reanalysis/history, invalid output, retry, stale/duplicate confirmation and isolation', flush=True)
    finally:
        os.environ.clear()
        os.environ.update(previous)
        get_settings.cache_clear()
