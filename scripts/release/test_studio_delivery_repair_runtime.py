"""Actual backend repair under SQLite/storage fixtures; never calls a model."""
import importlib.util
import json
from hashlib import sha256
from pathlib import Path
import sys
from uuid import UUID

import pytest

BACKEND = Path(__file__).resolve().parents[2] / 'hengxin-smart-image/backend'
sys.path[:0] = [str(BACKEND), str(BACKEND / 'tests')]
from test_studio_delivery_repair import historical
from test_studio_image_recovery import missed
from test_overseas_studio import studio
from test_overseas_materials import materials
from test_overseas_tasks import overseas
from test_overseas_assignment import change_roles
from app.overseas.execution.models import ExecutionGate, Job
from app.overseas.studio.models import Turn

spec = importlib.util.spec_from_file_location('delivery_repair_runtime',
    Path(__file__).with_name('studio-delivery-repair-runtime.py'))
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


@pytest.fixture(autouse=True)
def test_environment(monkeypatch):
    monkeypatch.setenv('APP_ENV', 'test')
    monkeypatch.setenv('ENABLE_DEV_IDENTITY', 'false')


@pytest.fixture
def eight(historical):
    case = historical
    work = case.events.parents[2] / 'persistent/work'
    expected = {}
    for index in range(8):
        name = f'original-{index}.png'
        (work / name).write_bytes(case.data)
        expected['/work/' + name] = sha256(case.data).hexdigest()
    reply = '\n'.join('![图片](' + name + ')' for name in expected)
    events = [dict(type='thread.started', thread_id='thread-1'), dict(type='turn.started'),
        dict(type='item.completed', item=dict(type='agent_message', text=reply)), dict(type='turn.completed')]
    raw = '\n'.join(json.dumps(row) for row in events).encode()
    case.events.write_bytes(raw)
    with case.factory.begin() as session:
        turn = session.get(Turn, UUID(case.turn['id']))
        turn.reply, turn.event_offset = reply, len(raw)
        job = session.get(Job, turn.job_id)
        job.result = {**job.result, 'reply': reply}
        session.get(ExecutionGate, 1).paused = False
    case.request = dict(actor_id=str(case.actor), turn_id=case.turn['id'],
        expected_sha256=sha256(raw).hexdigest(), expected_checksums=expected)
    return case


def run(case, action, **extras):
    return runtime.execute(dict(request=case.request, action=action, **extras), case.factory, case.store)


def gate(case):
    with case.factory() as session:
        return session.get(ExecutionGate, 1).paused


@pytest.mark.parametrize('original', [False, True])
def test_installed_runtime_pauses_repairs_eight_verifies_bytes_repeats_and_preserves_gate(eight, original):
    case = eight
    with case.factory.begin() as session:
        session.get(ExecutionGate, 1).paused = original
    before = run(case, 'inspect')
    assert before['paused'] is original
    assert run(case, 'pause', original_paused=original) == {'paused': True}
    assert run(case, 'dry-run')['status'] == 'eligible'
    assert run(case, 'apply')['status'] == 'succeeded'
    first = run(case, 'verify')
    assert len(first['objects']) == 8 and first['execution'] == before['execution']
    assert run(case, 'repeat')['status'] == 'already_recovered'
    assert run(case, 'verify-repeat') == first
    assert gate(case) is True
    assert run(case, 'restore', original_paused=original) == {'paused': original}
    assert gate(case) is original


def test_corrupt_stored_bytes_fail_verification_while_gate_stays_paused(eight):
    case = eight
    run(case, 'pause', original_paused=False)
    assert run(case, 'apply')['status'] == 'succeeded'
    result = run(case, 'verify')
    case.store.data[result['objects'][0]['key']] = b'corrupted storage'
    with pytest.raises(Exception, match='完整性校验失败'):
        run(case, 'verify-repeat')
    assert gate(case) is True


def test_gate_change_needs_existing_settings_authority(eight):
    case = eight
    change_roles(case.factory, case.actor, ('designer',))
    with pytest.raises(Exception):
        run(case, 'pause', original_paused=False)
    assert gate(case) is False


def test_pending_execution_forbids_pause_and_restore(eight):
    case = eight
    with case.factory.begin() as session:
        session.get(Job, UUID(case.turn['jobId'])).status = 'collecting'
    with pytest.raises(AssertionError, match='not drained'):
        run(case, 'pause', original_paused=False)
    assert gate(case) is False
    with case.factory.begin() as session:
        session.get(ExecutionGate, 1).paused = True
    with pytest.raises(AssertionError, match='not drained'):
        run(case, 'restore', original_paused=False)
    assert gate(case) is True
    assert run(case, 'hold') == {'paused': True}

