"""Regression checks for production scope boundaries, failed backups and historical rows."""
import copy
import hashlib
import json
from types import SimpleNamespace

import pytest

import overseas_design_history as history
import overseas_design_policy as policy


def manifests(monkeypatch):
    sources = {n: 'new' for n in policy.MIGRATIONS}
    sources['backend/app/execution/workspace.py'] = 'new'
    frontend = {'frontend/index.html': 'entry'}
    env = {'VITE_RELEASE_SCOPE': 'overseas', 'VITE_VERSION': policy.CANDIDATE[:12]}
    candidate = dict(scope='overseas', commit=policy.CANDIDATE, files={**sources, **frontend},
                     frontend_current_files=frontend, runtime_inputs={'binary': 'same'},
                     provenance={'source_commit': policy.CANDIDATE, 'source_files': dict(sources),
                                 'build': {'environment': env}})
    before = dict(commit=policy.BASE, files={}, runtime_inputs={'binary': 'same'})
    monkeypatch.setattr(policy, 'SOURCE_SHA', policy.digest(sources))
    monkeypatch.setattr(policy, 'FRONTEND_SHA', policy.digest(frontend))
    monkeypatch.setattr(policy, 'DELTA_SHA', policy.digest({n: [None, v] for n, v in sources.items()}))
    return before, candidate


def test_provenance_scopes_and_delta_are_pinned(monkeypatch):
    before, candidate = manifests(monkeypatch)
    assert policy.validate(before, candidate) == sorted(candidate['provenance']['source_files'])
    for key, value in [('scope', 'shared'), ('runtime_inputs', {}), ('provenance', {}),
                       ('files', {**candidate['files'], 'backend/unrelated': 'new'})]:
        with pytest.raises(RuntimeError):
            policy.validate(before, {**candidate, key: value})
    tampered = copy.deepcopy(candidate)
    tampered['provenance']['source_files']['frontend/src/changed.ts'] = 'added'
    with pytest.raises(RuntimeError):
        policy.validate(before, tampered)
    for scope, mode in [('domestic', 'full'), ('overseas', 'frontend'), ('shared', 'frontend')]:
        with pytest.raises(RuntimeError):
            policy.check(None, None, None, None, scope, mode)


def test_reject_relabeled_build_or_commit_and_replaced_page(monkeypatch):
    before, candidate = manifests(monkeypatch)
    candidate['files']['frontend/assets/old.js'] = 'retained-for-old-tabs'
    policy.validate(before, candidate)
    for changed in ('commit', 'scope', 'files', 'frontend_current_files'):
        altered = copy.deepcopy(candidate)
        if changed == 'commit':
            altered['commit'] = altered['provenance']['source_commit'] = '0' * 40
        elif changed == 'scope':
            altered['provenance']['build']['environment']['VITE_RELEASE_SCOPE'] = 'shared'
        else:
            altered[changed]['frontend/index.html'] = 'other-page'
        with pytest.raises(RuntimeError):
            policy.validate(before, altered)


def test_verified_existing_backup_is_rechecked(tmp_path, monkeypatch):
    folder = tmp_path / 'data-backup'
    folder.mkdir()
    archive = folder / 'overseas.dump'
    archive.write_bytes(b'original')
    report = folder / 'verified.json'
    report.write_text(json.dumps({'overseas': {'bytes': 8, 'sha256': history.operations.file_sha(archive)}}))
    u = SimpleNamespace(WORK=tmp_path, safe=lambda p: None, digest=lambda data: hashlib.sha256(data).hexdigest())
    monkeypatch.setattr(history.operations, 'backup', lambda *a, **kw: pytest.fail('Repeated backup'))
    assert history.backup(u, 9) == u.digest(report.read_bytes())
    archive.write_bytes(b'tampered')
    with pytest.raises(RuntimeError):
        history.backup(u, 9)


def test_changed_or_missing_historical_records_are_rejected(monkeypatch):
    old = {table: [1, 'old'] for table in history.HISTORY}
    monkeypatch.setattr(history, 'check_shape', lambda u, migrated: None)
    monkeypatch.setattr(history, 'sql', lambda u, q: 'SELECT\nINSERT\nUPDATE\nDELETE')
    monkeypatch.setattr(history, 'rows', lambda u: old)
    assert history.capture(None) == old
    history.verify(None, old)
    with pytest.raises(RuntimeError):
        history.verify(None, {**old, 'overseas_tasks': [1, 'different']})
    with pytest.raises(RuntimeError):
        history.verify(None, {'overseas_tasks': old['overseas_tasks']})
    monkeypatch.setattr(history, 'sql', lambda u, q: 'SELECT')
    with pytest.raises(RuntimeError, match='default grants'):
        history.capture(None)
