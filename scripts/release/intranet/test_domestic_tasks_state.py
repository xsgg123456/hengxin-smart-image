"""Durable marker/ledger crash-window checks without host mutations."""
from contextlib import nullcontext
import copy
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import catalog
import domestic_tasks_release as tasks
import engine
import snapshot


@pytest.fixture
def world(tmp_path, monkeypatch):
    old = {'schema': {'domestic': '0043', 'overseas': 'overseas_0026'}, 'backend': '/old'}
    item = {'before': copy.deepcopy(old), 'release': '/candidate', 'scope': 'domestic',
            'mode': 'full', 'work': str(tmp_path), 'target_backend': '/candidate',
            'target_frontend': '/candidate', 'phase': 'prepared'}
    data = {'current': old, 'pending': item, 'previous': None}
    store = SimpleNamespace(root=tmp_path, report=lambda name, value:
                            (tmp_path / name).write_text(json.dumps(value)))
    u = SimpleNamespace(WORK=tmp_path, safe=lambda p: None)
    monkeypatch.setattr(engine, 'u', u)
    upgrade = tasks.Upgrade(store)
    upgrade.tool = SimpleNamespace(load=lambda: copy.deepcopy(data),
        save=lambda value: (data.clear(), data.update(copy.deepcopy(value))),
        capture=lambda *a, **k: copy.deepcopy(data['current']), configure=lambda i: None,
        cleanup=Mock())
    monkeypatch.setattr(upgrade, 'configured', lambda *a: nullcontext())
    monkeypatch.setattr(tasks.fence, 'hold', lambda u: nullcontext(99))
    monkeypatch.setattr(snapshot, 'schemas', lambda u: copy.deepcopy(data['current']['schema']))
    monkeypatch.setattr(catalog, 'finished_attempt', Mock())
    row = {'release': '/candidate', 'item': copy.deepcopy(item),
           'before_sha256': catalog.state_sha(old)}
    upgrade.save(row, 'prepared')
    return upgrade, data, row, item


def test_unstarted_cancel_is_verified_and_clears_pending(world):
    upgrade, data, _, _ = world
    assert upgrade.recover()['phase'] == 'cancelled'
    assert data['pending'] is None
    upgrade.tool.cleanup.assert_not_called()


def test_crash_after_restore_ledger_save_reconciles_marker(world, monkeypatch):
    upgrade, data, row, item = world
    original = upgrade.save
    def crash(value, phase):
        if phase == 'cancelled':
            raise RuntimeError('crash after ledger saved')
        return original(value, phase)
    monkeypatch.setattr(upgrade, 'save', crash)
    with pytest.raises(RuntimeError, match='crash'):
        upgrade.recover()
    assert data['pending'] is None
    assert upgrade.read()['phase'] == 'restoring-ledger'
    monkeypatch.setattr(upgrade, 'save', original)
    assert upgrade.recover()['phase'] == 'cancelled'


def test_unknown_schema_never_attempts_forward_or_old_restore(world, monkeypatch):
    upgrade, data, _, _ = world
    data['current']['schema']['domestic'] = 'unknown'
    restore, resume = Mock(), Mock()
    monkeypatch.setattr(engine, 'recover', restore)
    monkeypatch.setattr(tasks.migration, 'resume', resume)
    with pytest.raises(RuntimeError, match='Unknown schema'):
        upgrade.recover()
    restore.assert_not_called()
    resume.assert_not_called()
    assert data['pending'] is not None


def test_preparing_without_pending_cannot_clear_live_drift(world):
    upgrade, data, row, _ = world
    data['pending'] = None
    row.pop('item')
    upgrade.save(row, 'preparing')
    data['current']['schema']['domestic'] = '0044'
    with pytest.raises(RuntimeError, match='baseline drift'):
        upgrade.recover()


def test_partial_pending_before_work_creation_can_cancel(world):
    upgrade, data, row, item = world
    data['pending']['work'] += '/not-created'
    row.pop('item')
    upgrade.save(row, 'preparing')
    assert upgrade.recover()['phase'] == 'cancelled'
    assert data['pending'] is None


def test_postcommit_recovery_never_calls_old_recover(world, monkeypatch):
    upgrade, data, _, _ = world
    data['current']['schema']['domestic'] = '0044'
    resume, restore = Mock(), Mock()
    monkeypatch.setattr(tasks.migration, 'resume', resume)
    monkeypatch.setattr(engine, 'recover', restore)
    monkeypatch.setattr(upgrade, 'finish', lambda: {'phase': 'complete'})
    assert upgrade.recover() == {'phase': 'complete'}
    assert upgrade.read()['phase'] == 'forward-required'
    resume.assert_called_once()
    restore.assert_not_called()
