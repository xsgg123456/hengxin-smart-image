"""0046 admits only the reviewed package and preserves the full historical row set."""
from types import SimpleNamespace

import pytest

import domestic_general_history as history
import domestic_general_policy as policy
import domestic_tasks_marker as markers
import domestic_workspaces_history as workspaces


def test_general_transition_interlocks_old_and_ordinary_publishers(tmp_path):
    adapter, store = SimpleNamespace(safe=lambda p: None), SimpleNamespace(root=tmp_path)
    (tmp_path / policy.MARKER).write_text('{"phase":"forward-required"}')
    with pytest.raises(RuntimeError, match='general-recover'):
        markers.guard(adapter, store, except_name=markers.workspaces.MARKER)
    markers.guard(adapter, store, except_name=policy.MARKER)


def test_general_history_verifies_constraints_and_digests(monkeypatch):
    seen = []
    monkeypatch.setattr(workspaces, 'check_values', lambda u, products, replacements:
                        seen.append((products, replacements)))
    monkeypatch.setattr(workspaces, 'rows', lambda u: {'tasks': [1, 'preserved']})
    before = history.capture(None)
    history.verify(None, before)
    assert seen[1][0] - seen[0][0] == {'general'}
    assert seen[0][1] == seen[1][1] == {'product', 'scene', 'phone', 'edit'}
    with pytest.raises(RuntimeError, match='historical rows changed'):
        history.verify(None, {'tasks': [1, 'changed']})


def test_general_policy_refuses_unreviewed_bytes_and_wrong_provenance():
    before = {'scope': 'domestic', 'commit': policy.BASE, 'files': {}}
    candidate = {'scope': 'domestic', 'commit':'c' * 40, 'provenance':{'source_commit':'c' * 40},
                 'files':{policy.MIGRATION: policy.MIGRATION_SHA}}
    with pytest.raises(RuntimeError, match='exactly the reviewed'):
        policy.validate(before, candidate)
    candidate['provenance'] = {}
    with pytest.raises(RuntimeError, match='Git provenance'):
        policy.validate(before, candidate)
    assert not policy.approved_change('backend/app/main.py', 'old', 'new')
