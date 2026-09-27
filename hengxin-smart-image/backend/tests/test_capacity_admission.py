from datetime import timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.capacity.admission import covered, pending_bytes, published, reserve
from app.capacity.models import CapacityGate, CapacityReservation
from app.capacity.observation import inspect_volumes, sample
from app.capacity.observe import enable
from app.models import Job, utcnow
from app.modules.api_image_edits.claims import claim as api_claim, start_attempt
from app.modules.api_image_edits.execution import execute_next
from app.modules.api_image_edits.models import ApiAttempt, ApiFile, ApiItem
from app.modules.api_image_edits.relay import RelayResult
from app.modules.tasks.claims import claim as cli_claim, sweep_expired
from app.modules.tasks.models import RoundRecord
from files_helpers import files_env, image_bytes
from test_api_image_domain import ROOT, create, enabled_api
from test_api_image_execution import Client, due
from test_tasks import task_env, submit, job_for

MIB = 1024 * 1024


def policy(factory, free=1000 * MIB):
    with factory.begin() as session:
        row = session.get(CapacityGate, 1)
        row.enabled, row.free_bytes, row.floor_bytes = True, free, 100 * MIB
        row.api_bytes, row.cli_bytes = 60 * MIB, 400 * MIB
        row.volumes, row.sample_at = {'test': 'isolated simulated sample'}, utcnow()


def test_api_no_capacity_means_no_model_or_attempt(files_env):
    web, factory, store, _ = files_env
    create(web, 1)
    policy(factory, free=159 * MIB)
    client = Client()
    assert not execute_next(factory, store, client)
    assert not client.calls
    with factory() as session:
        item = session.scalar(select(ApiItem))
        assert item.state == 'queued' and item.lease_token is None
        assert '等待存储容量' in item.error
        assert session.scalar(select(ApiAttempt)) is None
        assert pending_bytes(session) == 0


def test_late_guard_rejects_missing_reservation(files_env):
    web, factory, _, _ = files_env
    create(web, 1)
    claimed = api_claim(factory)  # old disabled admission
    policy(factory)
    assert not start_attempt(factory, claimed[0], claimed[1])
    with factory() as session:
        assert session.get(ApiItem, claimed[0]).state == 'queued'
        assert session.scalar(select(ApiAttempt)) is None


def test_paid_collection_survives_full_disk_stale_sample_and_ambiguous_put(files_env):
    web, factory, store, _ = files_env
    task, _ = create(web, 1)
    policy(factory)
    original_count = len(store.objects)
    store.fail_put = True  # MemoryStore writes bytes BEFORE throwing.
    client = Client()
    assert execute_next(factory, store, client)
    with factory.begin() as session:
        item = session.scalar(select(ApiItem))
        cycle, staging = item.capacity_cycle_id, item.staging_file_id
        assert session.get(CapacityReservation, cycle).state == 'held'
        row = session.get(CapacityGate, 1)
        row.free_bytes, row.sample_at = 0, utcnow() - timedelta(days=1)
    store.fail_put = False
    due(factory)
    assert execute_next(factory, store, client)
    assert len(client.calls) == 1 and len(store.objects) == original_count + 1
    assert web.get(ROOT + '/tasks/' + task).json()['status'] == 'succeeded'
    with factory() as session:
        item = session.scalar(select(ApiItem))
        assert item.capacity_cycle_id == cycle and item.result_id == staging
        assert session.get(CapacityReservation, cycle).state == 'published'
        assert pending_bytes(session) == 60 * MIB  # Publication is NOT reclamation.


def test_failed_receipt_delete_and_expired_lease_never_release(files_env):
    web, factory, store, _ = files_env
    task, _ = create(web, 1)
    policy(factory)
    client = Client([RelayResult(result_url='https://cdn3.dmiapi.com/result')])
    def broken(_):
        raise OSError('unavailable')
    for _ in range(4):
        assert execute_next(factory, store, client, broken)
        due(factory)
    assert web.delete(ROOT + '/tasks/' + task).status_code == 200
    with factory() as session:
        assert pending_bytes(session) == 60 * MIB
        assert session.scalar(select(ApiItem)).result_url
    create(web, 1)
    first = api_claim(factory)
    with factory.begin() as session:
        session.get(ApiItem, first[0]).lease_until = utcnow() - timedelta(seconds=1)
    assert api_claim(factory) is None
    with factory() as session:
        assert pending_bytes(session) == 120 * MIB


def test_revision_has_new_cycle_and_preserves_previous_debt(files_env):
    web, factory, store, _ = files_env
    task, _ = create(web, 1)
    policy(factory)
    assert execute_next(factory, store, Client())
    with factory() as session:
        item = session.scalar(select(ApiItem))
        previous = item.capacity_cycle_id
        path = f'{ROOT}/tasks/{task}/items/{item.id}'
    response = web.post(path + '/revise', json={'baseVersion': 1, 'text': '修改文字'},
                        headers={'Idempotency-Key': 'capacity-revise'})
    assert response.status_code == 202, response.text
    assert api_claim(factory)
    with factory() as session:
        assert session.scalar(select(ApiItem)).capacity_cycle_id != previous
        assert session.get(CapacityReservation, previous).state == 'published'
        assert pending_bytes(session) == 120 * MIB


def test_cli_and_api_share_budget_and_cli_uncertain_retains(task_env):
    web, factory, _, _ = task_env
    receipt = submit(task_env).json()
    create(web, 1)
    policy(factory, free=500 * MIB)
    job_id = job_for(factory, receipt)
    assert cli_claim(factory, job_id)
    assert api_claim(factory) is None
    with factory.begin() as session:
        session.get(Job, job_id).lease_until = utcnow() - timedelta(seconds=1)
    sweep_expired(factory)
    with factory() as session:
        assert session.get(RoundRecord, UUID(receipt['roundId'])).status == 'uncertain'
        assert pending_bytes(session) == 400 * MIB


def test_rollback_and_identity_mismatch(files_env):
    factory = files_env[1]
    policy(factory)
    identity, owner = uuid4(), uuid4()
    with pytest.raises(RuntimeError), factory.begin() as session:
        assert reserve(session, identity, 'api', owner, 40 * MIB)
        raise RuntimeError('business claim rolled back')
    with factory.begin() as session:
        assert pending_bytes(session) == 0
        assert reserve(session, identity, 'api', owner, 40 * MIB)
        assert reserve(session, identity, 'api', owner, 40 * MIB)
        assert not reserve(session, identity, 'cli', owner, 40 * MIB)
        assert not covered(session, identity, 'api', uuid4(), 40 * MIB)
        assert pending_bytes(session) == 60 * MIB


def test_sampling_accounts_only_published_and_keeps_physical_growth(files_env, tmp_path, monkeypatch):
    factory = files_env[1]
    paths = {name: str(tmp_path / name) for name in ('execution', 'objects', 'database')}
    for path in paths.values():
        from pathlib import Path
        Path(path).mkdir()
    records, real_free = inspect_volumes(paths)
    assert real_free > 0 and set(records) == set(paths)
    free = [1000 * MIB]
    monkeypatch.setattr('app.capacity.observation.shutil.disk_usage', lambda _: SimpleNamespace(free=free[0]))
    with factory.begin() as session:
        row = session.get(CapacityGate, 1)
        row.enabled, row.floor_bytes, row.api_bytes = True, 100 * MIB, 60 * MIB
        sample(session, paths)
        paid, unknown = uuid4(), uuid4()
        assert reserve(session, paid, 'api', paid, 40 * MIB)
        assert reserve(session, unknown, 'api', unknown, 40 * MIB)
        published(session, paid)
        assert pending_bytes(session) == 120 * MIB
    free[0] -= 30 * MIB  # Already stored originals still consume measured space.
    with factory.begin() as session:
        result = sample(session, paths)
        assert result['freeBytes'] == 970 * MIB and result['pendingBytes'] == 60 * MIB
        assert session.get(CapacityReservation, paid).state == 'accounted'
        assert session.get(CapacityReservation, unknown).state == 'held'
        assert not reserve(session, paid, 'api', paid, 40 * MIB)
        row = session.get(CapacityGate, 1)
        row.sample_at = utcnow() - timedelta(seconds=31)
        assert not reserve(session, uuid4(), 'api', uuid4(), 40 * MIB)
        assert covered(session, unknown, 'api', unknown, 40 * MIB)
    wrong = dict(paths, objects=str(tmp_path))
    with pytest.raises(ValueError, match='identity'), factory.begin() as session:
        sample(session, wrong)


def test_enable_requires_drain_and_explicit_actual_paths(task_env, tmp_path):
    web, factory, _, _ = task_env
    create(web, 1)
    assert api_claim(factory)
    paths = {name: str(tmp_path) for name in ('execution', 'objects', 'database')}
    with pytest.raises(ValueError, match='Drain'), factory.begin() as session:
        enable(session, paths, MIB, 60 * MIB, 400 * MIB)
    with pytest.raises(ValueError):
        inspect_volumes({'objects': str(tmp_path)})


def test_changed_retry_bytes_cannot_overwrite_staging(files_env):
    web, factory, store, _ = files_env
    create(web, 1)
    policy(factory)
    client = Client([RelayResult(result_url='https://cdn3.dmiapi.com/result')])
    store.fail_put = True
    assert execute_next(factory, store, client, lambda _: image_bytes())
    with factory() as session:
        item = session.scalar(select(ApiItem))
        record = session.get(ApiFile, item.staging_file_id)
        key, cycle = record.object_key, item.capacity_cycle_id
    store.fail_put = False
    due(factory)
    assert execute_next(factory, store, client, lambda _: image_bytes('JPEG'))
    assert store.objects[key] == image_bytes() and len(client.calls) == 1
    with factory() as session:
        assert session.scalar(select(ApiItem)).state == 'failed'
        assert session.get(CapacityReservation, cycle).state == 'held'


def test_drained_activation_and_sampling_never_enable_by_default(task_env, tmp_path, monkeypatch):
    factory = task_env[1]
    paths = {name: str(tmp_path) for name in ('execution', 'objects', 'database')}
    monkeypatch.setattr('app.capacity.observation.shutil.disk_usage', lambda _: SimpleNamespace(free=2000 * MIB))
    with factory.begin() as session:
        assert not sample(session, paths)['enabled']
    with pytest.raises(ValueError, match='envelopes'), factory.begin() as session:
        enable(session, paths, MIB, MIB, MIB)
    with factory.begin() as session:
        assert enable(session, paths, 100 * MIB, 60 * MIB, 400 * MIB)['enabled']
    with pytest.raises(ValueError, match='Already enabled'), factory.begin() as session:
        enable(session, paths, 100 * MIB, 60 * MIB, 400 * MIB)
