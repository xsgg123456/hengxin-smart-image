from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import restore_ingress as restore


@pytest.fixture
def world(monkeypatch):
    data = {'version': 2, 'pending': None, 'current': {'source': 'verified'}}
    row = {'phase': 'complete'}
    gates = {'workers': True, 'ingress': False}
    tool = SimpleNamespace(u=object(), store=SimpleNamespace(report=Mock()),
                           load=Mock(side_effect=lambda: deepcopy(data)),
                           capture=Mock(side_effect=lambda *a, **k: deepcopy(data['current'])))
    monkeypatch.setattr(restore.marker, 'read', lambda *args: deepcopy(row))
    monkeypatch.setattr(restore.scopes, 'has_domestic_publisher', lambda _: True)
    monkeypatch.setattr(restore.paths, 'gate_state', lambda _, name: gates[name])
    opened = Mock(side_effect=lambda _, name, value: gates.update({name: value}))
    monkeypatch.setattr(restore.paths, 'set_gate', opened)
    monkeypatch.setattr(restore.catalog, 'before', Mock())
    return tool, data, row, gates, opened


def test_verification_precedes_reopening_and_does_not_change_ledger(world):
    tool, data, _, gates, opened = world
    original = deepcopy(data)
    assert restore.restore(tool) == original
    assert gates == {'workers': True, 'ingress': True} and data == original
    tool.capture.assert_called_once_with(original, runtime=True)
    opened.assert_called_once_with(tool.u, 'ingress', True)
    assert tool.store.report.call_args.args[1]['phase'] == 'opened'


@pytest.mark.parametrize('case', ['pending', 'migration', 'incomplete', 'workers', 'source', 'ledger', 'gate'])
def test_failed_verification_never_opens(world, case):
    tool, data, row, gates, opened = world
    if case == 'pending': data['pending'] = {'phase': 'prepared'}
    elif case == 'migration': data['migration_pending'] = True
    elif case == 'incomplete': row['phase'] = 'opening'
    elif case == 'workers': gates['workers'] = False
    elif case == 'source': tool.capture.side_effect = lambda *a, **k: {'source': 'drift'}
    elif case == 'ledger': tool.load.side_effect = [deepcopy(data), dict(data, pending={'phase': 'prepared'})]
    else:
        def drift(*args, **kwargs):
            gates['workers'] = False
            return deepcopy(data['current'])
        tool.capture.side_effect = drift
    with pytest.raises(RuntimeError): restore.restore(tool)
    opened.assert_not_called()


def test_already_open_is_verified_without_writing(world):
    tool, _, _, gates, opened = world
    gates['ingress'] = True
    restore.restore(tool)
    tool.capture.assert_called_once()
    opened.assert_not_called()
    tool.store.report.assert_not_called()
