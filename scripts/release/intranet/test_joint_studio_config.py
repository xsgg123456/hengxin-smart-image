import copy
from pathlib import PurePosixPath
from types import SimpleNamespace

import pytest

import domestic_studio_wiring as wiring
import image_gc
import joint_studio_config as joint
import joint_studio_gate_wiring as gate_wiring
import scope_engine
import scope_snapshot
import scopes
from test_domestic_studio_wiring import original as domestic_original


def compose():
    services = domestic_original()['services']
    for name in {n for values in scopes.APPS.values() for n in values}:
        services.setdefault(name, {'volumes': [{'type': 'bind', 'source': '/old/app',
                                               'target': '/app/app', 'read_only': True}]})
    for name in gate_wiring.SERVICES:
        services[name].setdefault('environment', {})
    for scope in scopes.GROUPS:
        services[scopes.UI[scope]] = {'volumes': [{'type': 'bind', 'source': '/old/frontend',
                                                   'target': '/usr/share/nginx/html', 'read_only': True}]}
    services['domestic-web'] = {'volumes': []}
    services['domestic-postgres'] = {'volumes': []}
    return {'name': 'hengxin-lan', 'services': services}


def frontends():
    return {name: '/opt/hengxin-unified-releases/' + name for name in scopes.GROUPS}


def test_joint_candidate_switches_each_scope_without_mutating_infrastructure():
    source = compose()
    before = copy.deepcopy(source)
    root = '/opt/hengxin-unified-releases/release-backend'
    result = joint.candidate(source, SimpleNamespace(DATA={'domestic-postgres'}), root, frontends())
    assert source == before
    assert result['services']['domestic-web'] == before['services']['domestic-web']
    assert result['services']['domestic-postgres'] == before['services']['domestic-postgres']
    for scope in scopes.GROUPS:
        for name in scopes.APPS[scope]:
            mounts = result['services'][name]['volumes']
            app = [m for m in mounts if m['target'] == '/app/app']
            assert len(app) == 1 and app[0]['read_only']
            assert app[0]['source'] == str(PurePosixPath(root) / 'backend/app')
        ui = result['services'][scopes.UI[scope]]['volumes']
        current = next(row for row in ui if row['target'] == '/usr/share/nginx/html')
        previous = next(row for row in ui if row['target'] == '/usr/share/nginx/previous')
        assert current['source'] == str(PurePosixPath(frontends()[scope]) / 'frontend')
        assert previous['source'] == '/old/frontend' and previous['read_only']
    publisher = result['services'][wiring.PUBLISHER]
    assert next(v for v in publisher['volumes'] if v['target'] == '/app/app')['source'] == root + '/backend/app'


@pytest.mark.parametrize('bad', ['missing', 'duplicate', 'outside'])
def test_joint_candidate_rejects_unverifiable_frontends(bad):
    values = frontends()
    if bad == 'missing': values.pop('shared')
    elif bad == 'duplicate': values['shared'] = values['domestic']
    else: values['shared'] = '/tmp/untrusted'
    with pytest.raises(ValueError):
        joint.candidate(compose(), SimpleNamespace(DATA={'domestic-postgres'}),
                        '/opt/hengxin-unified-releases/backend', values)


def test_native_dropins_only_add_domestic_settings_to_relevant_services():
    root = '/opt/hengxin-unified-releases/backend'
    worker = joint.native_dropin('hengxin-vps-codex-worker', root).decode()
    cleanup = joint.native_dropin('hengxin-domestic-deletions', root).decode()
    other = joint.native_dropin('hengxin-overseas-worker', root).decode()
    assert worker == cleanup
    assert 'DOMESTIC_STUDIO_LOCK_ROOT=' + wiring.LOCKS in worker
    assert 'DOMESTIC_SKILL_ROOT=' + wiring.SKILLS in worker
    assert 'DOMESTIC_' not in other


def test_subsequent_scoped_release_preserves_and_tracks_publisher():
    u = SimpleNamespace(DATA={'domestic-postgres'})
    current = joint.candidate(compose(), u, '/opt/hengxin-unified-releases/backend', frontends())
    backend = PurePosixPath('/opt/hengxin-unified-releases/later')
    with pytest.raises(RuntimeError, match='inventory'):
        scope_engine.candidate(current, u, 'domestic', 'full', backend, backend)
    future = scope_engine.candidate(current, u, 'domestic', 'full', backend, backend, True)
    publisher = future['services'][wiring.PUBLISHER]
    assert next(v for v in publisher['volumes'] if v['target'] == '/app/app')['source'] == str(backend / 'backend/app')
    assert future['services']['overseas-api'] == current['services']['overseas-api']
    assert publisher['environment'] == current['services'][wiring.PUBLISHER]['environment']


def test_census_treats_publisher_as_domestic_only():
    before = {'containers': {wiring.PUBLISHER: {'id': 'old'}, 'overseas-api': {'id': 'overseas'}}, 'native': {}}
    after = {'containers': {wiring.PUBLISHER: {'id': 'new'}, 'overseas-api': {'id': 'overseas'}}, 'native': {}}
    scope_snapshot.unchanged_other(before, after, 'domestic')
    with pytest.raises(RuntimeError, match='Unaffected runtime'):
        scope_snapshot.unchanged_other(before, after, 'overseas')


def test_image_inventory_requires_the_added_service_only_after_recorded_upgrade():
    import engine
    legacy = image_gc.expected(image_gc.scoped(engine.u))
    upgraded = image_gc.expected(image_gc.scoped(engine.u, domestic_publisher=True))
    assert len(legacy) == 20 and len(upgraded) == 21
    assert upgraded - legacy == {wiring.PUBLISHER}
