"""Finish failures close domestic ingress and retries reverify before reopening."""
from contextlib import nullcontext
import copy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import domestic_tasks_release as tasks
import engine


@pytest.fixture
def finish_world(tmp_path, monkeypatch):
    entries = ('domestic-api', 'domestic-ui')
    live = {name: {'State': {'Running': True}} for name in (*entries, 'domestic-outbox')}
    commands = []
    def app(action, names):
        commands.append((action, tuple(names)))
        for name in names:
            live[name]['State']['Running'] = action == 'up'
    u = SimpleNamespace(WORK=tmp_path, ENTRIES=entries, containers=lambda: live,
                        app_command=app, safe=lambda p: None)
    monkeypatch.setattr(engine, 'u', u)
    upgrade = tasks.Upgrade(SimpleNamespace(root=tmp_path))
    item = {'before': {}, 'census': {}, 'scope': 'domestic', 'mode': 'full'}
    row = {'phase': 'deploying'}
    data = {'current': {}, 'pending': item}
    saves = []
    upgrade.tool = SimpleNamespace(load=lambda: copy.deepcopy(data), capture=Mock(return_value={}),
        save=lambda value: (data.clear(), data.update(copy.deepcopy(value))), cleanup=Mock())
    monkeypatch.setattr(upgrade, 'read', lambda: copy.deepcopy(row))
    monkeypatch.setattr(upgrade, 'item', lambda row: item)
    def save(value, phase):
        value['phase'] = phase
        row.update(value)
        saves.append(phase)
    monkeypatch.setattr(upgrade, 'save', save)
    monkeypatch.setattr(upgrade, 'configured', lambda *a: nullcontext())
    monkeypatch.setattr(tasks.scope_engine, 'context', lambda *a, **kw: nullcontext())
    monkeypatch.setattr(tasks.fence, 'hold', lambda u: nullcontext(99))
    monkeypatch.setattr(tasks.migration, 'check_migration', Mock())
    monkeypatch.setattr(tasks.migration, 'check_restarts', Mock())
    monkeypatch.setattr(engine, 'apply', Mock(return_value='applied'))
    monkeypatch.setattr(upgrade, 'verify_after', Mock())
    monkeypatch.setattr(tasks.catalog, 'advance', Mock())
    monkeypatch.setattr(tasks.catalog, 'check', Mock())
    monkeypatch.setattr(tasks.cleanup_history, 'sources', lambda state: set())
    (tmp_path / 'applied.json').write_text('{}')
    return upgrade, row, data, live, commands


@pytest.mark.parametrize('failure', ['capture', 'verify', 'catalog', 'ledger', 'marker'])
def test_failed_finish_closes_only_domestic_entries_and_preserves_pending(finish_world, monkeypatch, failure):
    upgrade, row, data, live, commands = finish_world
    fail = Mock(side_effect=RuntimeError('injected ' + failure))
    if failure == 'capture':
        monkeypatch.setattr(upgrade.tool, 'capture', fail)
    elif failure == 'verify':
        monkeypatch.setattr(upgrade, 'verify_after', fail)
    elif failure == 'catalog':
        monkeypatch.setattr(tasks.catalog, 'advance', fail)
    elif failure == 'ledger':
        monkeypatch.setattr(upgrade.tool, 'save', fail)
    else:
        monkeypatch.setattr(upgrade, 'save', fail)
    with pytest.raises(RuntimeError, match='injected'):
        upgrade.finish()
    assert commands == [('stop', ('domestic-api', 'domestic-ui'))]
    assert not live['domestic-api']['State']['Running'] and not live['domestic-ui']['State']['Running']
    assert live['domestic-outbox']['State']['Running']
    assert data['pending'] is not None and row['phase'] != 'complete'
    upgrade.tool.cleanup.assert_not_called()


def test_finish_retry_reopens_only_closed_entries_after_candidate_recheck(finish_world, monkeypatch):
    upgrade, row, data, live, commands = finish_world
    capture = upgrade.tool.capture
    capture.side_effect = RuntimeError('capture failed')
    with pytest.raises(RuntimeError):
        upgrade.finish()
    capture.side_effect = None
    def checked():
        assert commands == [('stop', ('domestic-api', 'domestic-ui'))]
        assert not live['domestic-api']['State']['Running']
        return 'applied'
    monkeypatch.setattr(engine, 'apply', checked)
    assert upgrade.finish()['phase'] == 'complete'
    assert commands[-1] == ('up', ('domestic-api', 'domestic-ui'))
    assert data['pending'] is None
    assert live['domestic-outbox']['State']['Running']
    tasks.migration.check_restarts.assert_called_once()


def test_failed_candidate_recheck_keeps_entries_closed(finish_world, monkeypatch):
    upgrade, row, data, live, commands = finish_world
    live['domestic-api']['State']['Running'] = False
    live['domestic-ui']['State']['Running'] = False
    monkeypatch.setattr(engine, 'apply', Mock(side_effect=RuntimeError('candidate drift')))
    with pytest.raises(RuntimeError, match='candidate drift'):
        upgrade.finish()
    assert commands == [('stop', ('domestic-api', 'domestic-ui'))]
    upgrade.tool.capture.assert_not_called()


def test_cleanup_error_after_confirmed_success_does_not_close_entries(finish_world):
    upgrade, row, data, live, commands = finish_world
    upgrade.tool.cleanup.side_effect = RuntimeError('cleanup failed')
    with pytest.raises(RuntimeError, match='cleanup failed'):
        upgrade.finish()
    assert row['phase'] == 'complete' and data['pending'] is None
    assert not commands


def test_marker_failure_after_ledger_write_closes_entries_and_reconciles_retry(finish_world, monkeypatch):
    upgrade, row, data, live, commands = finish_world
    save = upgrade.save
    def fail_complete(value, phase):
        if phase == 'complete':
            raise RuntimeError('completion marker interrupted')
        save(value, phase)
    monkeypatch.setattr(upgrade, 'save', fail_complete)
    with pytest.raises(RuntimeError, match='marker interrupted'):
        upgrade.finish()
    assert row['phase'] == 'ledger-writing' and data['pending'] is None
    assert commands == [('stop', ('domestic-api', 'domestic-ui'))]
    monkeypatch.setattr(upgrade, 'save', save)
    assert upgrade.finish()['phase'] == 'complete'
    assert commands[-1] == ('up', ('domestic-api', 'domestic-ui'))


def test_unconfirmed_entry_stop_never_clears_pending(finish_world, monkeypatch):
    upgrade, row, data, live, commands = finish_world
    upgrade.tool.capture.side_effect = RuntimeError('capture failure')
    monkeypatch.setattr(upgrade.u, 'app_command', Mock(side_effect=RuntimeError('entry stop failure')))
    with pytest.raises(RuntimeError, match='entry stop failure'):
        upgrade.finish()
    assert data['pending'] is not None and row['phase'] == 'deploying'
    upgrade.tool.cleanup.assert_not_called()
