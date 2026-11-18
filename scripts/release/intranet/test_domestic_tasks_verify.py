"""Tasks finish permits only prepared domestic compose/source-dropin hashes."""
import copy
from pathlib import Path
from types import SimpleNamespace

import pytest

import domestic_tasks_release as tasks
import engine
import scopes


@pytest.fixture
def verify_world(tmp_path, monkeypatch):
    u = SimpleNamespace(COMPOSE=Path('/opt/hengxin-lan/compose.json'),
                        SYSTEMD=Path('/etc/systemd/system'), DROPIN='90-unified-source.conf')
    monkeypatch.setattr(engine, 'u', u)
    baseline = {'candidate': 'new-compose', 'dropins': {n: 'new-' + n for n in scopes.NATIVE['domestic']}}
    monkeypatch.setattr(engine, '_read', lambda name: baseline)
    configs = {'/etc/hengxin-lan/hengxin-overseas-worker.env': 'old-env',
               '/etc/hengxin-lan/domestic.env': 'old-domestic-env',
               '/etc/nginx/gateway.conf': 'old-gateway', str(u.COMPOSE): 'old-compose'}
    for names in scopes.NATIVE.values():
        for name in names:
            configs[str(u.SYSTEMD / (name + '.service.d') / u.DROPIN)] = 'old-' + name
    before = {'configs': configs, 'schema': {'domestic': '0043', 'overseas': '0026'},
              'groups': {n: {'backend': '/old-' + n, 'frontend': '/old-' + n} for n in scopes.GROUPS},
              'asset_fallbacks': {n: '/previous-' + n for n in scopes.GROUPS},
              'native': {}, 'data': {}, 'images': {}, 'binaries': {}}
    # Group composition/census are independent checks; keep those stable here.
    monkeypatch.setattr(tasks.scope_snapshot, 'group', lambda state, side: state['groups'][side])
    monkeypatch.setattr(tasks.scope_snapshot, 'census', lambda *a, **kw: {'containers': {}, 'native': {}})
    item = {'before': before, 'release': '/candidate', 'target_backend': '/candidate',
            'census': {'containers': {}, 'native': {}}}
    after = copy.deepcopy(before)
    after['schema']['domestic'] = '0044'
    after['groups']['domestic'] = {'backend': '/candidate', 'frontend': '/candidate'}
    after['configs'][str(u.COMPOSE)] = baseline['candidate']
    for name, digest in baseline['dropins'].items():
        after['configs'][str(u.SYSTEMD / (name + '.service.d') / u.DROPIN)] = digest
    return tasks.Upgrade(SimpleNamespace(root=tmp_path)), item, after


def test_only_exact_prepared_domestic_config_changes_pass(verify_world):
    upgrade, item, after = verify_world
    upgrade.verify_after(item, after)


@pytest.mark.parametrize('operation', ['add', 'remove', 'change'])
@pytest.mark.parametrize('path', ['/etc/hengxin-lan/hengxin-overseas-worker.env',
                                  '/etc/hengxin-lan/domestic.env', '/etc/nginx/gateway.conf',
                                  str(Path('/etc/systemd/system/hengxin-codex-auth.service.d/90-unified-source.conf'))])
def test_unapproved_config_add_remove_change_refused(verify_world, operation, path):
    upgrade, item, after = verify_world
    if operation == 'add':
        after['configs'][path + '.unknown'] = 'unknown'
    elif operation == 'remove':
        del after['configs'][path]
    else:
        after['configs'][path] = 'tampered'
    with pytest.raises(RuntimeError, match='Live release drift'):
        upgrade.verify_after(item, after)


@pytest.mark.parametrize('path', [str(Path('/opt/hengxin-lan/compose.json')),
    str(Path('/etc/systemd/system/hengxin-vps-codex-worker.service.d/90-unified-source.conf'))])
def test_domestic_config_must_match_prepared_hash(verify_world, path):
    upgrade, item, after = verify_world
    after['configs'][path] = 'unreviewed-domestic-change'
    with pytest.raises(RuntimeError, match='Live release drift'):
        upgrade.verify_after(item, after)
