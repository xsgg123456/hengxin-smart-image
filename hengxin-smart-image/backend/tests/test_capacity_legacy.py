from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.capacity.admission import reserve, pending_bytes
from app.capacity.models import CapacityGate, CapacityReservation
from app.capacity.observe import enable
from app.modules.api_image_edits.execution import execute_next
from app.modules.api_image_edits.models import ApiItem
from app.worker import reconcile, repair_delivery
from files_helpers import files_env, image_bytes
from test_api_image_domain import ROOT, create, enabled_api
from test_api_image_execution import Client
from test_execution_reconcile import recovery, state
from test_repair_delivery import failed
from test_tasks import task_env

MIB = 1024 * 1024


def old_receipt(web, factory, count=1):
    task, _ = create(web, count)
    with factory.begin() as session:
        for item in session.scalars(select(ApiItem)):
            item.state, item.result_bytes = 'failed', image_bytes()
        from app.modules.api_image_edits.models import ApiTask
        from uuid import UUID
        session.get(ApiTask, UUID(task)).state = 'failed'
    return task


def test_activation_adopts_both_paid_legacy_paths_before_new_work(recovery, task_env, tmp_path, monkeypatch):
    failed(recovery, monkeypatch)
    factory, store = recovery[:2]
    task = old_receipt(task_env[0], factory)
    paths = {role: str(tmp_path) for role in ('execution', 'objects', 'database')}
    monkeypatch.setattr('app.capacity.observation.shutil.disk_usage', lambda _: SimpleNamespace(free=560 * MIB))
    with factory.begin() as session:
        result = enable(session, paths, 100 * MIB, 60 * MIB, 400 * MIB)
        assert result['legacyReservations'] == 2 and pending_bytes(session) == 460 * MIB
        assert not reserve(session, uuid4(), 'api', uuid4(), 40 * MIB)
    # Real accepted final delivery is recollected, not just a helper assertion.
    assert repair_delivery.prepare_recollection(factory, recovery[7])['images'] == 1
    reconcile.reconcile_once(factory, store)
    assert state(recovery)[0].status == 'succeeded' and state(recovery)[3] == 1
    assert state(recovery)[0].execution_count == 1
    assert task_env[0].post(ROOT + '/tasks/' + task + '/retry',
        headers={'Idempotency-Key': 'legacy-capacity-retry'}).status_code == 202
    client = Client()
    assert execute_next(factory, store, client)
    assert not client.calls
    with factory() as session:
        assert all(row.state == 'published' for row in session.scalars(select(CapacityReservation)))


def test_insufficient_legacy_debt_rolls_back_entire_activation(recovery, task_env, tmp_path, monkeypatch):
    failed(recovery, monkeypatch)
    factory = recovery[0]
    old_receipt(task_env[0], factory, count=2)
    paths = {role: str(tmp_path) for role in ('execution', 'objects', 'database')}
    monkeypatch.setattr('app.capacity.observation.shutil.disk_usage', lambda _: SimpleNamespace(free=600 * MIB))
    # 500 MiB available: CLI400 + API60 fits, the second API60 must roll all back.
    with pytest.raises(ValueError, match='legacy API'), factory.begin() as session:
        enable(session, paths, 100 * MIB, 60 * MIB, 400 * MIB)
    with factory() as session:
        policy = session.get(CapacityGate, 1)
        assert not policy.enabled and policy.volumes == {} and policy.sample_at is None
        assert pending_bytes(session) == 0
        assert all(item.capacity_cycle_id is None and item.result_bytes == image_bytes()
                   for item in session.scalars(select(ApiItem)))
    assert state(recovery)[0].status == 'failed' and state(recovery)[3] == 0
