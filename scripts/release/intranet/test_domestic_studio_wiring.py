import copy

import pytest

import domestic_studio_wiring as wiring


def original():
    return {'services': {'domestic-api': {
        'image': 'sha256:' + 'a' * 64, 'user': 'app', 'group_add': ['986'],
        'networks': {'domestic': {}},
        'environment': {'APP_ENV': 'production', 'DATABASE_URL': 'postgresql+psycopg://domestic-host/domestic',
                        'DINGTALK_CLIENT_SECRET': 'private-domestic-secret'},
        'volumes': [{'type': 'bind', 'source': '/old/app', 'target': '/app/app', 'read_only': True}]},
        'overseas-skill-publisher': {'environment': {'OVERSEAS_DATABASE_URL': 'postgresql+psycopg://overseas-host/overseas'}}}}


def test_wiring_is_pure_and_publisher_has_only_its_domestic_mounts_and_environment():
    source = original()
    before = copy.deepcopy(source)
    result = wiring.candidate(source, '/opt/hengxin-unified-releases/domestic-test')
    assert source == before
    api, publisher = result['services']['domestic-api'], result['services'][wiring.PUBLISHER]
    assert api['user'] == 'app' and api['environment']['DOMESTIC_STUDIO_LOCK_ROOT'] == wiring.LOCKS
    assert api['environment']['DOMESTIC_STUDIO_PROTECTED'] == '1'
    mounts = {row['target']: row for row in api['volumes']}
    assert mounts[wiring.SKILLS]['read_only'] and mounts[wiring.SOCKET_DIR]['read_only']
    assert not mounts[wiring.LOCKS]['read_only']
    assert publisher['user'] == '0:0' and publisher['read_only']
    assert 'ports' not in publisher and publisher['image'] == api['image']
    assert publisher['environment']['DATABASE_URL'] == api['environment']['DATABASE_URL']
    assert 'DINGTALK_CLIENT_SECRET' not in publisher['environment']
    assert 'OVERSEAS_DATABASE_URL' not in publisher['environment']
    assert all('overseas' not in row['source'] for row in publisher['volumes'])
    assert result['services']['overseas-skill-publisher'] == before['services']['overseas-skill-publisher']


@pytest.mark.parametrize('alter', ['publisher', 'lock_group', 'mount', 'database', 'release', 'image', 'env', 'same_db', 'dev_identity', 'test_jobs'])
def test_wiring_rejects_unverified_or_conflicting_inputs(alter):
    source = original()
    release = '/opt/hengxin-unified-releases/domestic-test'
    if alter == 'publisher': source['services'][wiring.PUBLISHER] = {}
    elif alter == 'lock_group': source['services']['domestic-api']['group_add'] = []
    elif alter == 'mount': source['services']['domestic-api']['volumes'].append({'target': wiring.LOCKS})
    elif alter == 'database': source['services']['domestic-api']['environment']['DATABASE_URL'] = 'sqlite:///file'
    elif alter == 'release': release = '/tmp/other'
    elif alter == 'image': source['services']['domestic-api']['image'] = 'latest'
    elif alter == 'env': source['services']['domestic-api']['environment']['DOMESTIC_SKILL_ROOT'] = '/wrong'
    elif alter == 'same_db': source['services']['overseas-skill-publisher']['environment']['OVERSEAS_DATABASE_URL'] = 'postgresql+psycopg://different:credentials@domestic-host:5432/domestic'
    elif alter == 'dev_identity': source['services']['domestic-api']['environment']['ENABLE_DEV_IDENTITY'] = 'true'
    else: source['services']['domestic-api']['environment']['ENABLE_TEST_JOBS'] = 'true'
    with pytest.raises(ValueError):
        wiring.candidate(source, release)


def test_legacy_development_runtime_receives_explicit_protection_without_changing_app_mode():
    source = original()
    source['services']['domestic-api']['environment']['APP_ENV'] = 'development'
    result = wiring.candidate(source, '/opt/hengxin-unified-releases/domestic-test')
    env = result['services']['domestic-api']['environment']
    assert env['APP_ENV'] == 'development' and env['DOMESTIC_STUDIO_PROTECTED'] == '1'
    assert wiring.native_environment()['DOMESTIC_STUDIO_PROTECTED'] == '1'
