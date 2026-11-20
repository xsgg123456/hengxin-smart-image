from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import hashlib
import json

import pytest

import design_shared_frontend as login


def package(scope):
    files = {'backend/app/main.py': 'a', 'frontend/index.html': scope}
    return dict(commit=login.COMMIT, scope=scope, files=files, frontend_current_files={'frontend/index.html': scope},
                runtime_inputs={'runtime': 'b'},
                provenance=dict(source_commit=login.COMMIT, source_files={'frontend/src/login.ts': 'c'},
                                build={'environment': {'VITE_RELEASE_SCOPE': scope}}))


def ledger():
    return {'pending': None, 'groups': {
        'shared': {'current': dict(backend_commit=login.SHARED_BASE, frontend_commit=login.SHARED_BASE,
                                   backend='/shared-old')},
        'overseas': {'current': dict(backend_commit=login.COMMIT, frontend_commit=login.COMMIT,
                                    schema={'overseas': 'overseas_0028'}, backend='/overseas-new')}}}


@pytest.fixture(autouse=True)
def pinned_assets(monkeypatch):
    data = json.dumps({'frontend/index.html': 'shared'}, sort_keys=True, separators=(',', ':')).encode()
    monkeypatch.setattr(login, 'SHARED_ASSETS', hashlib.sha256(data).hexdigest())


def test_same_commit_sources_and_scope_required():
    state, overseas, shared = ledger(), package('overseas'), package('shared')
    login.validate(state, overseas, shared)
    for mutate in (lambda s: s.update(scope='overseas'), lambda s: s.update(commit='other'),
                   lambda s: s['provenance']['source_files'].clear(),
                   lambda s: s['files'].update({'backend/app/main.py': 'changed'}),
                   lambda s: s['runtime_inputs'].clear(), lambda s: s['frontend_current_files'].clear(),
                   lambda s: s['files'].update({'frontend/index.html': 'other build'})):
        other = deepcopy(shared)
        mutate(other)
        with pytest.raises(RuntimeError):
            login.validate(state, overseas, other)
    state['groups']['overseas']['current']['schema']['overseas'] = 'overseas_0026'
    with pytest.raises(RuntimeError):
        login.validate(state, overseas, shared)


def test_ordinary_transaction_keeps_shared_backend(monkeypatch):
    candidate = Path('/shared-new')
    tool = SimpleNamespace(u=object(), load=ledger)
    monkeypatch.setattr(login.snapshot, 'release_path', lambda root: root)
    monkeypatch.setattr(login.catalog, 'check', lambda data: {'staged': {}})
    with pytest.raises(RuntimeError, match='staged'):
        login.prepare(tool, candidate)
    monkeypatch.setattr(login.catalog, 'check', lambda data: {'staged': {str(candidate): True}})
    monkeypatch.setattr(login.snapshot, 'manifest',
                        lambda u, root: package('shared' if root == candidate else 'overseas'))
    original = login.scope_changes.check

    def transaction(root, mode, scope):
        assert (root, mode, scope) == (candidate, 'frontend', 'shared')
        check = login.scope_changes.check
        assert check(tool.u, Path('/shared-old'), root, scope, mode) == []
        with pytest.raises(RuntimeError):
            check(tool.u, Path('/shared-old'), root, scope, 'full')
        return {'pending': {'mode': mode}}

    tool.prepare = transaction
    assert login.prepare(tool, candidate)['pending']['mode'] == 'frontend'
    assert login.scope_changes.check is original
