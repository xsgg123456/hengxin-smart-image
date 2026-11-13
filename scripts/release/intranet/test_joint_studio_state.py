import copy

import pytest

import joint_studio_state as joint
import scope_catalog
import scope_snapshot
import scopes
from test_scope_flow import world


@pytest.fixture
def transaction(world):
    old = world.tool.load()
    old['current']['schema'] = {'domestic': '0032', 'overseas': 'overseas_0026'}
    old['current']['asset_fallbacks'] = {name: {'source': old['current']['groups'][name]['frontend']}
                                          for name in scopes.GROUPS}
    for name, row in old['groups'].items():
        row['current'] = scope_snapshot.group(old['current'], name)
        row['previous'] = copy.deepcopy(row['current'])
        row['previous_work'] = '/old-transaction-' + name
    scope_catalog.seal(old)
    after = copy.deepcopy(old['current'])
    after['schema']['domestic'] = '0043'
    after['images'][scopes.DOMESTIC_PUBLISHER] = after['images']['domestic-api']
    backend = str(world.roots / 'candidate-backend')
    frontends = {name: str(world.roots / ('candidate-' + name)) for name in scopes.GROUPS}
    for name in scopes.GROUPS:
        after['groups'][name]['backend'] = backend
        after['groups'][name]['frontend'] = frontends[name]
        after['asset_fallbacks'][name]['source'] = old['current']['groups'][name]['frontend']
    parent = world.store.root / 'intranet-transactions'
    parent.mkdir()
    work = parent / 'joint-work'
    work.mkdir()
    (work / 'prepared.json').write_text('{}')
    return world, old, after, work, backend, frontends


def test_joint_success_seals_all_groups_and_pins_pre_migration_history(transaction):
    world, old, after, work, backend, frontends = transaction
    saved = copy.deepcopy(old)
    result = joint.advance(world.u, world.store, old, after, work, backend, frontends, set())
    assert old == saved
    assert result['current'] == after and not result['migration_pending']
    assert all(row['previous'] is None and row['current_work'] == str(work) for row in result['groups'].values())
    assert set(result['migration_work_pins']) >= {'/old-transaction-' + name for name in scopes.GROUPS}
    assert set(result['migration_pins']) >= {old['current']['groups'][name]['frontend'] for name in scopes.GROUPS}
    assert scopes.DOMESTIC_PUBLISHER in result['groups']['domestic']['current']['images']
    scope_catalog.check(result)


@pytest.mark.parametrize('case', ['schema', 'overseas_schema', 'data', 'native', 'image', 'publisher',
                                   'backend', 'frontend', 'fallback', 'config'])
def test_joint_success_refuses_unexpected_runtime_drift(transaction, case):
    world, old, after, work, backend, frontends = transaction
    if case == 'schema': after['schema']['domestic'] = '0042'
    elif case == 'overseas_schema': after['schema']['overseas'] = 'changed'
    elif case == 'data': after['data']['postgres'] = 'replaced'
    elif case == 'native': after['native']['hengxin-vps-codex-worker'] = {'python': 'other'}
    elif case == 'image': after['images']['overseas-api'] = 'different-image'
    elif case == 'publisher': after['images'][scopes.DOMESTIC_PUBLISHER] = 'different-image'
    elif case == 'backend': after['groups']['shared']['backend'] = '/unexpected'
    elif case == 'frontend': after['groups']['overseas']['frontend'] = '/unexpected'
    elif case == 'fallback': after['asset_fallbacks']['domestic']['source'] = '/unexpected'
    else: after['configs']['/unexpected'] = 'changed'
    with pytest.raises(RuntimeError):
        joint.advance(world.u, world.store, old, after, work, backend, frontends, set())
