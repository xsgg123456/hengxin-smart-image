"""Exercise forward continuation after the real post-migration probe failure."""
import ast
import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from test_native_studio_deploy import d, s, m, h, save, deployment, deploy


@pytest.fixture
def recovery(deployment, monkeypatch):
    work, source, events, fail = deployment
    fail['at'] = 'installed'
    with pytest.raises(RuntimeError):
        deploy(deployment)
    failure = json.loads((work / 'FAILURE.json').read_text())
    failure['errorType'] = 'AssertionError'
    save(work / 'FAILURE.json', failure)
    data = json.loads((work / 'topology.json').read_text())
    data['overseas']['mounts'] = {d.u.API: []}
    for group in m.GROUPS:
        data[group].update(ids={}, files={})
    save(work / 'topology.json', data)
    save(work / 'overseas-overlay.json', s.overlay(source, 'sha256:tested'))
    save(m.EDGE, h.closed_config((work / 'edge-before.conf').read_text()))
    monkeypatch.setattr(m, 'live', Mock(return_value={'State': {'Running': False}, 'Image': 'sha256:tested', 'Mounts': []}))
    monkeypatch.setattr(h, 'wait_empty', lambda *a: events.append(('idle',)))
    fail['at'] = None
    events.clear()
    return deployment


def recover(fixture):
    work, source, _, _ = fixture
    d.recover(work, source, {'release': 'fixture', 'files': {}}, 'image')


def test_forward_recovery_uses_tested_runtime_without_migration_or_backup_restore(recovery):
    work, _, events, _ = recovery
    recover(recovery)
    names = [e[0] for e in events]
    assert 'migration' not in names and 'backup' not in names and 'switch' not in names
    assert names.index('closed') < names.index('idle') < names.index('compose') < names.index('installed')
    assert names.index('installed') < names.index('publish') < names.index('open')
    assert (work / 'PHASE').read_text() == 'complete'
    assert (work / 'RECOVERY_STARTED').exists()
    assert json.loads((work / 'verification.json').read_text())['overseasMigration'] == s.NEW_SCHEMA
    assert all(e[1] == 'overseas' and e[2] == 'up' for e in events if e[0] == 'compose')
    assert not any('restore' in str(e) or 'systemctl' in str(e) for e in events)


@pytest.mark.parametrize('marker,value', [('PHASE', 'migration'), ('MIGRATION_VERIFIED', s.OLD_SCHEMA),
    ('PREPARED', 'sha256:drift'), ('RECOVERY_STARTED', 'already attempted'), ('INSTALLED_VERIFIED', 'done')])
def test_bad_state_blocks_api_start(recovery, marker, value):
    work, _, events, _ = recovery
    save(work / marker, value)
    with pytest.raises(AssertionError):
        recover(recovery)
    assert not any(e[0] == 'compose' for e in events)


def test_missing_backup_blocks_recovery(recovery):
    work, source, events, _ = recovery
    (source / 'backups/fixture/COMPLETE').unlink()
    with pytest.raises(AssertionError):
        recover(recovery)
    assert not any(e[0] == 'compose' for e in events)


@pytest.mark.parametrize('failure', ['compose', 'installed', 'public'])
def test_recovery_failure_keeps_intake_closed(recovery, failure):
    work, _, events, fail = recovery
    fail['at'] = failure
    with pytest.raises(RuntimeError):
        recover(recovery)
    report = json.loads((work / 'FAILURE.json').read_text())
    assert report['edgeClosed'] is True
    assert events[-1] == ('compose', 'overseas', 'stop', '-t', '30', 'api')
    assert not (work / 'verification.json').exists()


def test_recovery_rejects_changed_runtime_or_open_edge(recovery):
    work, _, events, _ = recovery
    m.live.return_value['State']['Running'] = True
    with pytest.raises(AssertionError):
        recover(recovery)
    assert not any(e[0] == 'compose' for e in events)
    m.live.return_value['State']['Running'] = False
    save(m.EDGE, (work / 'edge-before.conf').read_text())
    with pytest.raises(AssertionError):
        recover(recovery)
    assert not any(e[0] == 'compose' for e in events)


def test_studio_auth_probes_match_actual_registered_get_routes():
    router = Path(__file__).parents[2] / 'hengxin-smart-image/backend/app/overseas/studio/router.py'
    tree = ast.parse(router.read_text(encoding='utf-8'))
    prefix = next(kw.value.value for node in ast.walk(tree) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Name) and node.func.id == 'APIRouter'
                  for kw in node.keywords if kw.arg == 'prefix')
    paths = {prefix + node.args[0].value for node in ast.walk(tree) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Attribute) and node.func.attr == 'get'}
    normalized = {path.replace('{task_id}', '00000000-0000-0000-0000-000000000000') for path in paths}
    for probe in (s.STUDIO_ROUTE, s.STUDIO_ROUTE + '/transcript'):
        assert '/api/overseas/v1/' + probe in normalized
        assert probe in s.AUTH_ROUTES
