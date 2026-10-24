"""Historical repair uses original evidence and the normal durable collector."""
from datetime import timedelta
from hashlib import sha256
from uuid import UUID

import pytest
from sqlalchemy import func, select

from app.db.timestamps import utcnow
from app.overseas.execution import reconcile, runner
from app.overseas.execution.models import Job, JobOutbox
from app.overseas.management.models import Audit
from app.overseas.studio import delivery_recovery, delivery_repair
from app.overseas.studio.models import Picture
from app.overseas.tasks import cleanup_process
from app.overseas.tasks.models import ExecutionObject
from test_studio_image_recovery import missed
from test_overseas_studio import studio
from test_overseas_materials import materials
from test_overseas_tasks import overseas, ROOT


@pytest.fixture
def historical(missed, monkeypatch):
    (missed.events.parents[2] / 'persistent/work').mkdir(parents=True)
    monkeypatch.setattr(cleanup_process, 'group_alive', lambda _job: False)
    monkeypatch.setattr(delivery_repair, 'group_alive', lambda _job: False)
    monkeypatch.setattr(delivery_recovery, 'get_store', lambda: missed.store)
    monkeypatch.setattr(runner, 'execute', lambda *_args: pytest.fail('Repair must not invoke the model'))
    return missed


def repair(case, **kwargs):
    return delivery_repair.repair(case.factory, case.turn['id'], case.actor,
        kwargs.pop('event_hash', case.digest),
        kwargs.pop('image_hashes', {case.target: sha256(case.data).hexdigest()}),
        store=case.store, **kwargs)


def facts(case):
    with case.factory() as session:
        job = session.get(Job, UUID(case.turn['jobId']))
        outbox = session.get(JobOutbox, job.id)
        return job.completed_at, job.execution_count, job.started_at, outbox.completed_at


def count(case, model):
    with case.factory() as session:
        return session.scalar(select(func.count()).select_from(model))


def final_turn(case):
    response = case.client.get(ROOT + '/tasks/' + case.task['id'] + '/studio')
    assert response.status_code == 200, response.text
    return response.json()['turns'][-1]


def test_historical_dry_run_apply_and_repeat_preserve_execution_facts(historical):
    case = historical
    before, stored = facts(case), dict(case.store.data)
    controls = sorted(str(path.relative_to(case.events.parent)) for path in case.events.parent.rglob('*'))
    report = repair(case)
    assert report['status'] == 'eligible' and report['expected'] == 1 and report['saved'] == 0
    assert report['checksums'] == {case.target: sha256(case.data).hexdigest()}
    assert facts(case) == before and case.store.data == stored
    assert count(case, Picture) == count(case, Audit) == count(case, ExecutionObject) == 0
    assert sorted(str(path.relative_to(case.events.parent)) for path in case.events.parent.rglob('*')) == controls
    assert repair(case, apply=True)['status'] == 'succeeded'
    view = final_turn(case)
    assert view['status'] == 'succeeded' and view['deliveryError'] is None
    assert view['deliveryStatus'] == dict(state='complete', expected=1, saved=1)
    picture = view['pictures'][0]
    assert case.client.get(picture['url']).content == case.data
    assert facts(case) == before
    stored = dict(case.store.data)
    assert repair(case, apply=True)['status'] == 'already_recovered'
    assert count(case, Picture) == count(case, Audit) == count(case, ExecutionObject) == 1
    assert final_turn(case)['pictures'] == [picture] and case.store.data == stored and facts(case) == before


@pytest.mark.parametrize('mismatch', ['events', 'image', 'selection'])
def test_unapproved_event_or_image_hash_never_writes(historical, mismatch):
    case = historical
    before, stored = facts(case), dict(case.store.data)
    kwargs = {'event_hash': '0' * 64} if mismatch == 'events' else {
        'image_hashes': {case.target: '0' * 64} if mismatch == 'image' else {}}
    with pytest.raises(ValueError, match='digest changed|bytes or selection changed'):
        repair(case, apply=True, **kwargs)
    assert facts(case) == before and case.store.data == stored
    assert count(case, Picture) == count(case, Audit) == count(case, ExecutionObject) == 0
    assert not (case.events.parent / 'delivery-context.json').exists()


def test_repair_storage_fault_resumes_via_regular_reconcile_without_model(historical, monkeypatch):
    case = historical
    before, put = facts(case), case.store.put

    def unavailable(*_args):
        raise OSError('object store unavailable')

    monkeypatch.setattr(case.store, 'put', unavailable)
    assert repair(case, apply=True)['status'] == 'saving'
    assert final_turn(case)['status'] == 'collecting' and count(case, Picture) == 0
    assert count(case, ExecutionObject) == count(case, Audit) == 1
    case.image.write_bytes(b'overwritten after original bytes were snapshotted')
    with case.factory.begin() as session:
        job = session.get(Job, UUID(case.turn['jobId']))
        job.lease_until = utcnow() - timedelta(seconds=1)
        job.result = {**job.result, 'deliveryRetryAt': job.lease_until.isoformat()}
    monkeypatch.setattr(case.store, 'put', put)
    reconcile.reconcile_once(case.factory)
    view = final_turn(case)
    assert view['status'] == 'succeeded' and len(view['pictures']) == 1
    assert case.client.get(view['pictures'][0]['url']).content == case.data
    assert facts(case) == before
    stored = dict(case.store.data)
    reconcile.reconcile_once(case.factory)
    assert case.store.data == stored and count(case, Picture) == 1
