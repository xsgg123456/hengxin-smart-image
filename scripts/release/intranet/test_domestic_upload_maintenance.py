"""Exercise gateway maintenance with real on-disk release state and bound writes."""
import copy
import json
import os
from unittest.mock import Mock

import pytest

import domestic_upload_maintenance as maintenance
import domestic_tasks_marker
import release_cli
import scope_catalog
import snapshot
import split_config
from test_domestic_upload_routes import GATEWAY
from test_scope_flow import world


@pytest.fixture
def gateway(world, monkeypatch):
    w = world
    path = w.u.ROOT / 'nginx.conf'
    path.write_bytes(GATEWAY)
    monkeypatch.setattr(maintenance, 'BASELINE_SHA', snapshot.sha(GATEWAY))
    if os.name == 'nt':
        monkeypatch.setattr(split_config.os, 'O_NOFOLLOW', 0, raising=False)
    w.path = path
    w.inode = [path.stat().st_dev, path.stat().st_ino]
    w.initial = w.tool.load()
    w.initial['current']['configs'][str(path)] = snapshot.sha(GATEWAY)
    scope_catalog.seal(w.initial)
    w.tool.save(w.initial)
    capture = w.tool.capture

    def capture_gateway(data, runtime):
        current = capture(data, runtime=runtime)
        current['configs'][str(path)] = snapshot.sha(path.read_bytes())
        return current

    monkeypatch.setattr(w.tool, 'capture', capture_gateway)
    monkeypatch.setattr(maintenance, 'binding', lambda tool: [path.stat().st_dev, path.stat().st_ino])
    monkeypatch.setattr(maintenance, 'check_candidate', Mock())
    w.loaded = GATEWAY

    def reload_gateway(u):
        w.loaded = path.read_bytes()

    def probes(enabled):
        assert (w.loaded != GATEWAY) == enabled
        return {'task': 401 if enabled else 413, 'workspace': 401 if enabled else 413, 'control': 413}

    monkeypatch.setattr(split_config, 'reload_gateway', reload_gateway)
    monkeypatch.setattr(maintenance, 'verify_probes', probes)
    return w


def test_apply_and_rollback_preserve_inode_groups_and_later_success(gateway):
    w = gateway
    candidate = maintenance.domestic_upload_routes.render(GATEWAY)
    assert maintenance.run(w.tool, 'apply')['changed']
    assert w.loaded == w.path.read_bytes() == candidate
    assert not maintenance.run(w.tool, 'apply')['changed']
    applied = w.tool.load()
    scope_catalog.check(applied)
    assert applied['groups'] == w.initial['groups']
    # A later scoped release can change its own history between apply and rollback.
    applied['groups']['overseas']['previous_work'] = 'recorded-after-upload-maintenance'
    scope_catalog.seal(applied)
    w.tool.save(applied)
    assert maintenance.run(w.tool, 'rollback')['changed']
    assert not maintenance.run(w.tool, 'rollback')['changed']
    restored = w.tool.load()
    scope_catalog.check(restored)
    assert restored['groups'] == applied['groups']
    assert restored['current'] == w.initial['current']
    assert w.loaded == w.path.read_bytes() == GATEWAY
    assert [w.path.stat().st_dev, w.path.stat().st_ino] == w.inode


@pytest.mark.parametrize('failure', ['pending', 'migration', 'baseline', 'snapshot', 'syntax'])
def test_failed_preflight_performs_no_writes(gateway, monkeypatch, failure):
    w = gateway
    data = copy.deepcopy(w.initial)
    if failure == 'pending':
        data['pending'] = {'kind': 'another-release'}
    if failure == 'migration':
        data['migration_pending'] = True
    if failure == 'baseline':
        w.path.write_bytes(GATEWAY + b'# changed\n')
    if failure == 'snapshot':
        data['current']['configs'][str(w.path)] = 'unrelated'
        scope_catalog.seal(data)
    if failure == 'syntax':
        monkeypatch.setattr(maintenance, 'check_candidate', Mock(side_effect=RuntimeError('invalid nginx')))
    before = w.path.read_bytes()
    w.tool.save(data)
    with pytest.raises(RuntimeError):
        maintenance.run(w.tool, 'apply')
    assert w.tool.load() == data
    assert w.path.read_bytes() == before and w.loaded == GATEWAY


@pytest.mark.parametrize('action', ['apply', 'rollback'])
@pytest.mark.parametrize('failure', ['partial-write', 'reload', 'probe'])
def test_failure_restores_last_verified_state(gateway, monkeypatch, action, failure):
    w = gateway
    if action == 'rollback':
        maintenance.run(w.tool, 'apply')
    baseline, ledger = w.loaded, w.tool.load()
    if failure == 'partial-write':
        write = split_config.bound_write

        def interrupted(u, path, target, expected):
            if target != baseline:
                with path.open('r+b') as output:
                    output.write(target[:200])
                raise OSError('interrupted bound write')
            return write(u, path, target, expected)

        monkeypatch.setattr(split_config, 'bound_write', interrupted)
    if failure == 'reload':
        reload_gateway = split_config.reload_gateway

        def reload(u):
            if w.path.read_bytes() != baseline:
                raise RuntimeError('failed to signal nginx')
            reload_gateway(u)

        monkeypatch.setattr(split_config, 'reload_gateway', reload)
    if failure == 'probe':
        verify = maintenance.verify_probes

        def probe(enabled):
            if enabled == (action == 'apply'):
                raise RuntimeError('unexpected response status')
            return verify(enabled)

        monkeypatch.setattr(maintenance, 'verify_probes', probe)
    with pytest.raises((OSError, RuntimeError)):
        maintenance.run(w.tool, action)
    assert w.tool.load() == ledger
    assert w.loaded == w.path.read_bytes() == baseline


def test_recovery_persists_and_refuses_unrelated_config(gateway, monkeypatch):
    w = gateway
    with monkeypatch.context() as stopped:
        stopped.setattr(split_config, 'reload_gateway', Mock(side_effect=RuntimeError('offline')))
        with pytest.raises(RuntimeError, match='offline'):
            maintenance.run(w.tool, 'apply')
    pending = w.tool.load()
    assert pending['pending']['phase'] == 'restoring'
    with pytest.raises(RuntimeError):
        maintenance.run(w.tool, 'apply')
    w.path.write_bytes(b'unrelated local administrator change')
    with pytest.raises(RuntimeError, match='drift'):
        maintenance.run(w.tool, 'recover')
    assert w.tool.load() == pending and w.path.read_bytes() == b'unrelated local administrator change'
    w.path.write_bytes(GATEWAY)
    assert not maintenance.run(w.tool, 'recover')['enabled']
    assert w.tool.load() == w.initial


@pytest.mark.parametrize('options', [['--scope', 'overseas'], ['--apply'], ['--mode', 'full'],
                                     ['--release', '/somewhere']])
def test_cli_refuses_shared_release_options_before_any_io(options):
    with pytest.raises(SystemExit):
        release_cli.run(Mock(), ['upload-apply', *options])


def test_cli_interlocks_both_directions(gateway):
    w = gateway
    cli = Mock()
    cli.socket.gethostname.return_value = 'hengxin-ai-245'
    cli.os.geteuid.return_value = 0
    cli.engine.u = w.u
    cli.retention_store.return_value = w.store
    cli.Release.return_value = w.tool
    pending = copy.deepcopy(w.initial)
    pending['pending'] = {'phase': 'switching', 'kind': maintenance.KIND}
    w.tool.save(pending)
    for command in ('deploy', 'recover', 'cancel', 'cleanup', 'tasks-prepare', 'workspaces-deploy'):
        with pytest.raises(RuntimeError, match='upload-recover'):
            release_cli.run(cli, [command])
    assert w.tool.load() == pending
    w.tool.save(w.initial)
    marker = w.store.root / domestic_tasks_marker.NAME
    marker.write_text(json.dumps({'phase': 'deploying'}))
    with pytest.raises(RuntimeError, match='tasks-recover'):
        release_cli.run(cli, ['upload-apply'])
    assert w.tool.load() == w.initial and w.path.read_bytes() == GATEWAY
