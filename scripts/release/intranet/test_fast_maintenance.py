"""Exact reviewed bytes, closed ordinary boundary, and existing scoped recovery."""
import json
from pathlib import Path

import pytest

from test_scope_changes import releases
from test_scope_flow import world
import fast_maintenance as fast
import scope_changes
import snapshot


@pytest.fixture
def pair(releases, monkeypatch):
    base, _, write, u = releases
    old = b'def run():\n    args = ["exec"]\n'
    new = old + b'    args = ["-c", \'service_tier="priority"\', "-c", "features.fast_mode=true", *args]\n'
    monkeypatch.setattr(fast, 'BEFORE', snapshot.sha(old))
    monkeypatch.setattr(fast, 'AFTER', snapshot.sha(new))
    base.update({fast.PATH: old,
        'backend/app/main.py': b'import app.overseas.execution.runner\n',
        'backend/app/overseas/execution/worker.py': b'import app.overseas.execution.runner\n'})

    def create(scope='domestic', extra=None, candidate_meta=None):
        before = write('before', base)
        after = write('after', {**base, fast.PATH: new, **(extra or {})})
        path = after / 'release-manifest.json'
        manifest = json.loads(path.read_bytes())
        manifest.update(scope=scope, commit=fast.COMMIT)
        manifest.update(candidate_meta or {})
        path.write_text(json.dumps(manifest))
        return u, before, after
    return create


@pytest.mark.parametrize('scope', ['domestic', 'overseas'])
def test_only_explicit_maintenance_accepts_exact_shared_change(pair, scope):
    u, before, after = pair(scope)
    with pytest.raises(RuntimeError, match='shared/joint'):
        scope_changes.check(u, before, after, scope, 'full')
    assert scope_changes.check(u, before, after, scope, 'full', True) == [fast.PATH]


@pytest.mark.parametrize('meta', [{'commit': 'a'*40}, {'scope': 'shared'}])
def test_wrong_commit_or_scope_refused(pair, meta):
    u, before, after = pair(candidate_meta=meta)
    with pytest.raises(RuntimeError, match='reviewed scoped Fast'):
        scope_changes.check(u, before, after, 'domestic', 'full', True)


@pytest.mark.parametrize('scope,mode', [('shared', 'full'), ('domestic', 'frontend')])
def test_wrong_mode_or_group_refused(pair, scope, mode):
    u, before, after = pair(scope)
    with pytest.raises(RuntimeError, match='reviewed scoped Fast'):
        scope_changes.check(u, before, after, scope, mode, True)


def test_changed_runner_bytes_refused(pair):
    u, before, after = pair(extra={fast.PATH: b'def run(): pass\n'})
    with pytest.raises(RuntimeError, match='reviewed scoped Fast'):
        scope_changes.check(u, before, after, 'domestic', 'full', True)


def test_other_shared_changes_remain_refused(pair):
    u, before, after = pair(extra={'backend/app/identity/main.py': b'VALUE = 2\n'})
    with pytest.raises(RuntimeError, match='identity/main.py'):
        scope_changes.check(u, before, after, 'domestic', 'full', True)


def test_dependencies_remain_refused(pair):
    u, before, after = pair(extra={'backend/uv.lock': b'new dependency\n'})
    with pytest.raises(RuntimeError, match='Dependency/schema'):
        scope_changes.check(u, before, after, 'domestic', 'full', True)


def test_unknown_old_digest_refused(pair, monkeypatch):
    u, before, after = pair()
    monkeypatch.setattr(fast, 'BEFORE', '0'*64)
    with pytest.raises(RuntimeError, match='shared/joint'):
        scope_changes.check(u, before, after, 'domestic', 'full', True)


@pytest.mark.parametrize('failure', [None, 'drain', 'no-switch'])
def test_maintenance_uses_scoped_ledger_backup_and_recovery(world, monkeypatch, failure):
    w = world
    before = w.tool.load()
    root = w.make('fast', 'domestic')
    # Source checker is exercised with real manifests above; here spy on wiring.
    calls = []
    monkeypatch.setattr(scope_changes, 'check', lambda *a, **kw: calls.append(kw))
    data = w.tool.prepare(root, 'full', 'domestic', fast_maintenance=True)
    assert calls == [{'fast_maintenance': True}]
    assert data['pending']['maintenance'] == 'codex-fast-20261113'
    w.failure = failure
    if failure:
        with pytest.raises(RuntimeError):
            w.tool.deploy()
        w.tool.recover()
        assert w.tool.load()['current'] == before['current']
    else:
        data = w.tool.deploy()
        assert data['last']['maintenance'] == 'codex-fast-20261113'
        assert data['groups']['domestic']['previous'] == before['groups']['domestic']['current']
        assert data['groups']['overseas'] == before['groups']['overseas']
        assert data['groups']['shared'] == before['groups']['shared']
    assert w.backups == ['domestic']
