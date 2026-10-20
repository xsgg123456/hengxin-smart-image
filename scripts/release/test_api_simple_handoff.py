import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location('handoff', Path(__file__).with_name('api-simple-handoff.py'))
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)


def item(state='queued', **changes):
    return dict(id='item1', state=state, token=False, lease=False, expired=False, receipt=False, **changes)


def evidence(*items):
    return dict(paused=True, reserved=0, attempts=0, cli=0, unknown_tasks=0, items=list(items))


@pytest.mark.parametrize('state', ['queued', 'retry_wait', 'succeeded', 'failed'])
def test_durable_unleased_and_terminal_items_are_safe(state):
    assert h.safe(evidence(item(state)))


def test_receipted_collection_and_expired_uncertain_are_preserved():
    rows = [item('collecting'), item('uncertain')]
    rows[0]['receipt'] = True
    rows[1].update(id='item2', token=True, lease=True, expired=True)
    data = evidence(*rows)
    before = json.dumps(data, sort_keys=True)
    assert h.safe(data)
    assert json.dumps(data, sort_keys=True) == before


@pytest.mark.parametrize('state', ['running', 'unrecognized', 'collecting', 'uncertain'])
def test_unsafe_or_unknown_item_states_are_rejected(state):
    assert not h.safe(evidence(item(state)))


@pytest.mark.parametrize('state', ['queued', 'retry_wait', 'collecting', 'succeeded', 'failed', 'uncertain'])
@pytest.mark.parametrize('token,lease,expired', [
    (True, True, False), (True, False, False), (False, True, True),
])
def test_live_or_malformed_leases_are_rejected(state, token, lease, expired):
    row = item(state)
    row.update(token=token, lease=lease, expired=expired, receipt=True)
    assert not h.safe(evidence(row))


@pytest.mark.parametrize('key', ['reserved', 'attempts', 'cli', 'unknown_tasks'])
def test_other_active_or_unknown_work_blocks_handoff(key):
    data = evidence(item())
    data[key] = 1
    assert not h.safe(data)


@pytest.mark.parametrize('paused', [False, None, 't', 1])
def test_pause_must_be_confirmed_as_a_database_boolean(paused):
    data = evidence(item())
    data['paused'] = paused
    with pytest.raises(AssertionError, match='not paused'):
        h.safe(data)


@pytest.mark.parametrize('field,value', [('attempts', False), ('cli', -1), ('items', {}),
                                       ('reserved', None), ('unknown_tasks', '0')])
def test_malformed_database_evidence_fails_closed(field, value):
    data = evidence(item())
    data[field] = value
    with pytest.raises(AssertionError, match='Malformed'):
        h.safe(data)


def test_handoff_order_and_post_stop_recheck(monkeypatch, tmp_path):
    events = []
    runtime = SimpleNamespace(r=SimpleNamespace(sql=lambda _: 't'),
        graceful_stop=lambda service: events.append(service),
        m=SimpleNamespace(private=lambda path, value: events.append(path.name)))
    monkeypatch.setattr(h, 'wait_idle', lambda *_: events.append('stable-idle'))
    monkeypatch.setattr(h, 'database', lambda *_: evidence(item('queued')))
    h.drain(tmp_path, runtime)
    assert events == ['api-image-outbox', 'stable-idle', 'api-image-worker',
                      'api-handoff-stopped.json', 'EXECUTORS_STOPPED']
    events.clear()
    monkeypatch.setattr(h, 'database', lambda *_: evidence(item('running')))
    with pytest.raises(AssertionError, match='changed after'):
        h.drain(tmp_path, runtime)
    assert 'EXECUTORS_STOPPED' not in events


def test_pause_failure_never_stops_an_executor(tmp_path):
    runtime = SimpleNamespace(r=SimpleNamespace(sql=lambda _: 'f'),
        graceful_stop=lambda _: pytest.fail('must not stop'))
    with pytest.raises(AssertionError):
        h.drain(tmp_path, runtime)


def test_idle_requires_two_successive_observations(monkeypatch, tmp_path):
    samples = iter([True, False, True, True])
    writes = []
    runtime = SimpleNamespace(probe=SimpleNamespace(idle=lambda _: next(samples)),
        m=SimpleNamespace(private=lambda path, value: writes.append(value)))
    monkeypatch.setattr(h, 'broker', lambda *_: {})
    monkeypatch.setattr(h, 'database', lambda *_: evidence(item()))
    monkeypatch.setattr(h.time, 'sleep', lambda _: None)
    h.wait_idle(tmp_path, runtime)
    assert [row['stable'] for row in writes] == [1, 0, 1, 2]


def test_busy_timeout_does_not_return_safe(monkeypatch, tmp_path):
    times = iter([0, 0, 0.1, 0.2, 0.3, 2])
    runtime = SimpleNamespace(probe=SimpleNamespace(idle=lambda _: False),
        m=SimpleNamespace(private=lambda *_: None))
    monkeypatch.setattr(h, 'broker', lambda *_: {})
    monkeypatch.setattr(h, 'database', lambda *_: evidence(item()))
    monkeypatch.setattr(h.time, 'monotonic', lambda: next(times))
    monkeypatch.setattr(h.time, 'sleep', lambda _: None)
    with pytest.raises(AssertionError, match='busy/unknown'):
        h.wait_idle(tmp_path, runtime, 1)


def test_previously_completed_rows_cannot_change_or_disappear(monkeypatch):
    monkeypatch.setattr(h, 'protected', lambda _: {'api_image_items': {'old': 'same', 'new': 'new'}})
    h.verify_protected(None, {'api_image_items': {'old': 'same'}})
    for saved in ({'old': 'changed'}, {'gone': 'same'}):
        with pytest.raises(AssertionError, match='completed API evidence'):
            h.verify_protected(None, {'api_image_items': saved})
