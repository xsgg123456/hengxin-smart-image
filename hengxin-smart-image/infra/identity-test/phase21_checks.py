"""Real migrated overseas DB, Redis publication and authenticated execution HTTP."""
from contextlib import ExitStack
import os
from uuid import UUID, uuid4
from sqlalchemy.orm import sessionmaker
from app.core.config import get_settings
from app.overseas.execution import queue, claims
from app.overseas.execution.models import Job
from phase19_fixtures import domestic_snapshot


def run(h):
    previous = os.environ.copy()
    os.environ.update(h.environment('overseas'))
    get_settings.cache_clear()
    factory = sessionmaker(h.ENGINES['overseas'], expire_on_commit=False)
    before = domestic_snapshot(h)
    base = h.BUSINESS['overseas'][0] + '/api/overseas/v1'
    try:
        with ExitStack() as stack:
            clients = []
            for code in ('p18-operator', 'p18-designer', 'p19-designer2', 'p18-admin'):
                client = stack.enter_context(h.login(code))
                h.exchange(client, 'overseas')
                clients.append(client)
            operator, designer, replacement, admin = clients
            uid = h.expect(designer.get(base + '/auth/me'), 200).json()['id']
            new_uid = h.expect(replacement.get(base + '/auth/me'), 200).json()['id']
            task = h.expect(operator.post(base + '/tasks', headers={'Idempotency-Key': str(uuid4())},
                json=dict(name='执行隔离验收', productName='测试产品', brand='HX', platform='Amazon',
                          market='US', remarks='', skus=[{'code': 'P21'}], designerId=uid)), 201).json()
            task_id = UUID(task['id'])
            with factory.begin() as session:
                job_id = queue.enqueue(session, task_id, 'analysis', str(uuid4()), {'input': 'test only'}).id
            assert queue.dispatch_once(factory) == 1
            from redis import Redis
            redis = Redis.from_url(get_settings().redis_url)
            try:
                assert redis.llen('overseas.cli') == 1
            finally:
                redis.close()
            path = base + '/tasks/' + task['id']
            jobs = h.expect(designer.get(path + '/jobs'), 200).json()['items']
            assert len(jobs) == 1 and jobs[0]['status'] == 'queued'
            first = h.expect(designer.get(path + '/execution-events'), 200).json()
            assert len(first['items']) == 1
            token = claims.claim(factory, job_id)
            assert token
            follow = h.expect(designer.get(path + '/execution-events', params={'after': first['cursor']}), 200).json()
            assert len(follow['items']) == 1 and follow['items'][0]['status'] == 'running'
            stop = base + '/jobs/' + str(job_id) + '/cancel'
            h.expect(operator.post(stop, json={'version': 2}), 403)
            h.expect(designer.post(stop, json={'version': 1}), 409)
            result = h.expect(designer.post(stop, json={'version': 2}), 200).json()
            assert result['status'] == 'cancelling'
            assert not claims.finish(factory, job_id, token, 'cancelled')
            with factory.begin() as session:
                session.get(Job, job_id).process_exited = True
            assert claims.finish(factory, job_id, token, 'cancelled')
            h.expect(admin.patch(path + '/assignment', headers={'Idempotency-Key': str(uuid4())},
                                 json={'designerId': new_uid, 'version': task['version']}), 200)
            h.expect(designer.get(path + '/jobs'), 403)
            h.expect(designer.get(path + '/execution-events'), 403)
            h.expect(replacement.get(path + '/jobs'), 200)
            assert domestic_snapshot(h) == before
            print('PASS real execution Redis/outbox, HTTP cursor, cancel/version, reassignment and domestic isolation', flush=True)
    finally:
        os.environ.clear()
        os.environ.update(previous)
        get_settings.cache_clear()
