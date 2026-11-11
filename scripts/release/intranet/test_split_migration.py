"""Static migration contracts and reversible migration state machine, offline."""
import copy
import json
import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import catalog
import full_cleanup
import image_gc
import migrate_split
import scope_snapshot
import scopes
import snapshot
import split_config
import split_state
from test_scope_flow import world


GATEWAY = b'''server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;
    location /api/v1/ {
        proxy_set_header Host $host;
        proxy_pass http://domestic-api:8000;
    }
    location /api/overseas/v1/ {
        proxy_pass http://overseas-api:8000;
    }
    location /api/identity/v1/ {
        proxy_pass http://identity-api:8000;
    }
    location / {
        try_files $uri $uri/ /index.html;
    }
}
'''


@pytest.fixture
def migration(world, monkeypatch):
    w = world
    legacy = w.make('legacy-live', 'legacy')
    old_source = w.make('legacy-previous', 'legacy')
    config = json.loads(w.u.COMPOSE.read_bytes())
    for name in scopes.UI.values():
        config['services'].pop(name)
        w.inventory.pop(name)
    for name in w.u.PYTHON_SERVICES:
        config['services'][name]['volumes'][0]['source'] = str(legacy / 'backend/app')
    config['services']['domestic-web'].update(
        container_name='hengxin-lan-domestic-web', ports=['192.168.1.245:8080:80'],
        networks={'default': {'aliases': ['domestic-web']}},
        volumes=[{'type': 'bind', 'source': str(legacy / 'frontend'),
                  'target': '/usr/share/nginx/html', 'read_only': True}],
        restart='unless-stopped', environment={'UNCHANGED': 'yes'})
    config['networks'] = {'default': {'name': 'hengxin-lan-default'}}
    config['volumes'] = {'database': {'external': True}}
    config['x-preserved'] = {'ordered': [3, 1, 2], 'enabled': False}
    w.u.COMPOSE.write_text(json.dumps(config))
    (w.u.ROOT / 'nginx.conf').write_bytes(GATEWAY)
    manifest = json.loads((legacy / 'release-manifest.json').read_bytes())
    live = dict(backend=str(legacy), frontend=str(legacy), backend_commit=manifest['commit'],
                frontend_commit=manifest['commit'],
                backend_manifest=snapshot.sha((legacy / 'release-manifest.json').read_bytes()),
                frontend_manifest=snapshot.sha((legacy / 'release-manifest.json').read_bytes()),
                images=image_gc.capture(w.u), native={n: {'python': 'unchanged'} for n in w.native},
                binaries={}, schema={'domestic': 'schema-domestic', 'overseas': 'schema-overseas'},
                data=w.u.data_identity(), configs={})
    old_work = w.store.root / 'intranet-transactions/real-legacy-success'
    old_work.mkdir(parents=True)
    (old_work / 'applied.json').write_text('{"legacy": true}')
    prior_work = old_work.parent / 'real-legacy-previous'
    prior_work.mkdir()
    (prior_work / 'applied.json').write_text('{}')
    previous = dict(live, backend=str(old_source), frontend=str(old_source))
    retention = dict(version=1, current=catalog.record(live, live['images'], str(old_work)),
                     previous=catalog.record(previous, previous['images'], str(prior_work)),
                     known_images=sorted(set(live['images'].values())), artifacts={}, staged={}, unowned=[])
    for work in (old_work, prior_work):
        catalog.add_artifact(w.u, w.store, retention, work, 'transaction', [str(work)])
    old = dict(version=1, current=live, previous=previous, pending=None,
               last={'work': str(old_work), 'release': str(legacy)}, retention=retention,
               source_history=[str(legacy), str(old_source)])
    packages = {s: w.make('migration-' + s, s) for s in scopes.GROUPS}
    for scope, source in packages.items():
        archive = w.u.ROOT / (scope + '.tar.gz')
        archive.write_bytes(b'offline archive boundary')
        catalog.stage(w.u, w.store, old, source, archive)
    w.tool.save(old)
    monkeypatch.setattr(snapshot, 'capture', lambda u, runtime=False: copy.deepcopy(live))
    if os.name == 'nt':
        monkeypatch.setattr(split_config.os, 'O_NOFOLLOW', 0, raising=False)
    # The only simulated commands are Docker/nginx boundaries. Real compose and
    # gateway bytes, checksums, bound writes, ledgers and state transitions remain.
    original_run = w.u.run
    w.commands = []
    def run(argv, **kwargs):
        w.commands.append(argv)
        if argv[:3] == ['docker', 'ps', '-aq'] and '--filter' in argv:
            name = argv[-1].removeprefix('name=^hengxin-lan-').removesuffix('$')
            return w.inventory[name]['Id'] if name in w.inventory else ''
        if argv[:2] == ['docker', 'inspect']:
            return json.dumps([v for v in w.inventory.values() if v['Id'] in argv[2:]])
        if argv[:2] == ['docker', 'rm']:
            for name, value in list(w.inventory.items()):
                if value['Id'] == argv[2]:
                    del w.inventory[name]
            return ''
        if argv[:2] in (['docker', 'stop'], ['docker', 'run'], ['docker', 'exec']):
            return ''
        return original_run(argv, **kwargs)
    w.u.run = run
    def compose(*args, config):
        w.commands.append(['compose', *args])
        if args[0] == 'up':
            assert set(args[5:]) == set(scopes.UI.values())
            candidate = json.loads(Path(config).read_bytes())
            for scope, name in scopes.UI.items():
                info = copy.deepcopy(w.inventory['domestic-web'])
                info.update(Id='id-' + name, Name='/hengxin-lan-' + name)
                info['Config']['Labels']['com.docker.compose.service'] = name
                info['Mounts'] = [{'Destination': v['target'], 'Source': v['source'], 'RW': False}
                                  for v in candidate['services'][name]['volumes']]
                w.inventory[name] = info
    w.u.compose = compose
    w.migration = migrate_split.Migration(w.store)
    w.old, w.packages, w.legacy, w.config = old, packages, legacy, config
    return w


def test_compose_only_adds_three_static_services_without_mutating_original(migration):
    w = migration
    before = copy.deepcopy(w.config)
    result = split_config.compose(w.u, w.config, w.packages)
    assert w.config == before
    assert set(result['services']) - set(before['services']) == set(scopes.UI.values())
    assert {k: v for k, v in result.items() if k != 'services'} == {k: v for k, v in before.items() if k != 'services'}
    for name, service in before['services'].items():
        assert json.dumps(result['services'][name]) == json.dumps(service)
    for scope, name in scopes.UI.items():
        service = result['services'][name]
        assert 'ports' not in service
        assert service['image'] == before['services']['domestic-web']['image']
        assert service['networks']['default']['aliases'] == [name]
        assert service['volumes'][1]['source'] == str(w.packages[scope] / 'frontend')


def test_gateway_preserves_api_paths_legacy_assets_and_dynamic_dns():
    result = split_config.gateway(GATEWAY).decode()
    assert 'resolver 127.0.0.11 valid=5s ipv6=off;' in result
    for route, service in (('/api/v1/', 'domestic-api'), ('/api/overseas/v1/', 'overseas-api'),
                            ('/api/identity/v1/', 'identity-api')):
        assert 'location ' + route + ' {' in result
        assert 'set $upstream http://' + service + ':8000;' in result
    assert result.count('proxy_pass $upstream;') == 3
    assert 'proxy_set_header Host $host;' in result
    assert 'location ^~ /assets/ { try_files $uri =404; }' in result
    assert 'root /usr/share/nginx/html;' in result
    for scope in scopes.GROUPS:
        assert f'location = /{scope} {{ return 302 /{scope}/$is_args$args; }}' in result
        assert f'location ^~ /{scope}/ {{ set $ui http://{scope}-ui:80; proxy_pass $ui; }}' in result
    assert 'location / { set $ui http://shared-ui:80; proxy_pass $ui; }' in result
    with pytest.raises(RuntimeError, match='Unexpected'):
        split_config.gateway(result.encode())


@pytest.mark.parametrize('path', ['backend/app/main.py', 'backend/uv.lock'])
def test_first_migration_refuses_any_backend_change_before_writing_receipt(migration, path):
    w = migration
    root = w.packages['domestic']
    manifest = json.loads((root / 'release-manifest.json').read_bytes())
    manifest['files'][path] = 'different'
    (root / 'release-manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(RuntimeError, match='backend changes'):
        w.migration.prepare(w.packages)
    assert not (w.store.root / migrate_split.NAME).exists()
    assert not w.commands or all(cmd[0] == 'docker' and cmd[1] in ('ps', 'inspect') for cmd in w.commands)
    assert w.tool.load() == w.old


def test_migration_imports_real_legacy_current_and_protects_its_transaction(migration):
    w = migration
    before_census = scope_snapshot.census(w.u, independent=False)
    row = w.migration.prepare(w.packages)
    result = w.migration.apply()
    assert result['phase'] == 'complete'
    data = w.tool.load()
    assert data['version'] == 2 and data['migration_pending'] is False
    assert data['previous'] is None and data['last'] is None
    for scope, group in data['groups'].items():
        assert group['current']['frontend'] == str(w.packages[scope])
        assert group['current']['backend'] == str(w.legacy)
        for key in ('backend', 'frontend', 'backend_commit', 'frontend_commit', 'backend_manifest', 'frontend_manifest'):
            assert group['previous'][key] == w.old['current'][key]
        assert group['previous']['frontend'] != w.old['previous']['frontend']
        assert group['previous_work'] == w.old['last']['work']
        assert group['current_work'] == row['work']
        assert group['last'] is None
    sources, paths = catalog.protected(data)
    assert str(w.legacy) in sources and w.old['last']['work'] in paths
    assert row['work'] in paths
    assert not data['retention']['staged']
    split_state.unchanged_original(before_census, scope_snapshot.census(w.u))
    assert w.migration.finish()['phase'] == 'complete'
    assert not any(cmd[:2] == ['docker', 'stop'] for cmd in w.commands)
    assert w.migration.rollback()['phase'] == 'rolled-back'
    assert w.tool.load() == w.old
    assert json.loads(w.u.COMPOSE.read_bytes()) == w.config
    assert (w.u.ROOT / 'nginx.conf').read_bytes() == GATEWAY
    assert set(w.inventory).isdisjoint(scopes.UI.values())
    stopped = {cmd[-1] for cmd in w.commands if cmd[:2] == ['docker', 'stop']}
    assert stopped == {'id-' + n for n in scopes.UI.values()}


def test_gateway_failure_rolls_back_bytes_and_ledger_without_cleaning(migration, monkeypatch):
    w = migration
    w.migration.prepare(w.packages)
    calls = []
    def reload(u):
        calls.append(True)
        if len(calls) == 1:
            raise RuntimeError('nginx reload failed')
    monkeypatch.setattr(split_config, 'reload_gateway', reload)
    with pytest.raises(RuntimeError, match='nginx reload failed'):
        w.migration.apply()
    assert w.migration.read()['phase'] == 'rolled-back'
    assert w.tool.load() == w.old
    assert json.loads(w.u.COMPOSE.read_bytes()) == w.config
    assert (w.u.ROOT / 'nginx.conf').read_bytes() == GATEWAY
    assert w.cleanups == []
    assert Path(w.old['last']['work']).exists()


def test_migration_rejects_original_process_restart_before_switch(migration):
    w = migration
    w.migration.prepare(w.packages)
    w.native['hengxin-overseas-worker']['ExecMainStartTimestampMonotonic'] = 'changed'
    with pytest.raises(RuntimeError, match='existing running service'):
        w.migration.apply()
    assert json.loads(w.u.COMPOSE.read_bytes()) == w.config
    assert w.tool.load() == w.old


def test_migration_backup_drift_refuses_before_service_commands(migration):
    w = migration
    row = w.migration.prepare(w.packages)
    (Path(row['work']) / 'compose.candidate.json').write_bytes(b'foreign')
    with pytest.raises(RuntimeError, match='drift'):
        w.migration.apply()
    assert not any(cmd[0] == 'compose' for cmd in w.commands)
    assert w.tool.load() == w.old


def test_unverified_migration_blocks_gc_before_any_runtime_scan(migration):
    w = migration
    data = copy.deepcopy(w.old)
    data['migration_pending'] = True
    w.commands.clear()
    with pytest.raises(RuntimeError, match='Unverified migration'):
        full_cleanup.execute(w.u, w.store, data, apply=True)
    assert w.commands == []


@pytest.mark.parametrize('phase', ['ui-starting', 'ui-ready', 'gateway-switching'])
def test_interrupted_migration_requires_verified_finish_or_rollback(migration, phase):
    w = migration
    row = w.migration.prepare(w.packages)
    w.migration.save(row, phase)
    w.commands.clear()
    with pytest.raises(RuntimeError, match='Interrupted migration'):
        w.migration.apply()
    assert w.commands == []
    assert w.tool.load() == w.old
