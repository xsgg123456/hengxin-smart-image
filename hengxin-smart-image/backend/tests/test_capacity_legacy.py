from test_api_cli_conversation import seed_gate
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.capacity.admission import reserve, pending_bytes
from app.capacity.models import CapacityGate, CapacityReservation
from app.capacity.observe import enable
from app.modules.api_image_edits.execution import execute_next
from app.modules.api_image_edits.models import ApiItem
from files_helpers import files_env, image_bytes
from test_api_image_domain import ROOT, create, enabled_api
from test_api_image_execution import Client

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


def test_activation_adopts_paid_api_receipts_before_new_work(files_env, tmp_path, monkeypatch):
    web, factory, store, _ = files_env
    task = old_receipt(files_env[0], factory)
    paths = {role: str(tmp_path) for role in ('execution', 'objects', 'database')}
    monkeypatch.setattr('app.capacity.observation.shutil.disk_usage', lambda _: SimpleNamespace(free=560 * MIB))
    with factory.begin() as session:
        result = enable(session, paths, 100 * MIB, 60 * MIB, 400 * MIB)
        assert result['legacyReservations'] == 1 and pending_bytes(session) == 60 * MIB
        assert not reserve(session, uuid4(), 'api', uuid4(), 401 * MIB)
    assert files_env[0].post(ROOT + '/tasks/' + task + '/retry',
        headers={'Idempotency-Key': 'legacy-capacity-retry'}).status_code == 202
    client = Client()
    assert execute_next(factory, store, client)
    assert not client.calls
    with factory() as session:
        assert all(row.state == 'published' for row in session.scalars(select(CapacityReservation)))


def test_insufficient_legacy_debt_rolls_back_entire_activation(files_env, tmp_path, monkeypatch):
    factory = files_env[1]
    old_receipt(files_env[0], factory, count=9)
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
