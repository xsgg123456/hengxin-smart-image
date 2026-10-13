"""Configuration preservation, edge precedence, installed hashes and restore isolation."""
import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location('member_topology_tests', Path(__file__).with_name('member-release-runtime.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
b = m.module('member-release-backup')
v = m.module('member-release-verify')


def test_live_mount_order_does_not_report_drift_but_all_fields_still_matter(monkeypatch):
    original = {'Id': 'same-container', 'Mounts': [
        {'Destination': '/data', 'Source': '/existing/data', 'RW': True, 'Type': 'bind'},
        {'Destination': '/skills', 'Source': '/existing/skills', 'RW': False, 'Type': 'bind'}]}
    response = copy.deepcopy(original)
    monkeypatch.setattr(m, 'run', lambda *args, **kwargs: json.dumps([response]))
    baseline = m.live('api')
    response['Mounts'].reverse()
    assert m.live('api') == baseline
    for field, value in (('Source', '/different'), ('RW', True), ('Type', 'volume')):
        response = copy.deepcopy(original)
        response['Mounts'][1][field] = value
        assert m.live('api') != baseline
    response = copy.deepcopy(original)
    response['Mounts'].pop()
    assert m.live('api') != baseline


def test_edge_closure_overrides_domestic_regex_and_is_idempotent():
    original = '''server {
    ssl_prefer_server_ciphers off;
    location ^~ /api/identity/v1/ { proxy_pass http://identity; }
    location ^~ /api/overseas/v1/ { proxy_pass http://overseas; }
    location ~ ^/api/v1/tasks/[^/]+/events$ { proxy_pass http://sse; }
    location / { proxy_pass http://frontend; }
}'''
    changed = m.closed_config(original)
    assert changed.count('return 503;') == 3
    assert 'location ^~ /api/v1/ { return 503; }' in changed
    assert 'location ~ ^/api/v1/tasks/[^/]+/events$ { proxy_pass http://sse; }' in changed
    assert 'location / { proxy_pass http://frontend; }' in changed
    assert m.closed_config(changed) == changed


@pytest.mark.parametrize('body', ('location / { proxy_pass http://frontend; }',
    'location ^~ /api/identity/v1/ {} location ^~ /api/identity/v1/ {}'))
def test_edge_unknown_or_duplicate_layout_refused(body):
    with pytest.raises(AssertionError):
        m.closed_config(body)


@pytest.mark.parametrize('environment', (None, '/opt/release/overseas.env'))
def test_compose_uses_label_project_and_directory_with_optional_env(monkeypatch, environment):
    calls = []
    monkeypatch.setattr(m, 'run', lambda *args, **kwargs: calls.append((args, kwargs)))
    data = dict(project='existing', cwd='/opt/hengxin-smart-image/infra', env=environment, paths=['/opt/old.yaml'])
    m.compose(data, 'config', '--quiet', overlay=Path('/opt/new.json'))
    args, options = calls[0]
    assert args[:4] == ('docker', 'compose', '-p', 'existing')
    assert options['cwd'] == data['cwd']
    assert args[args.index('--project-directory') + 1] == data['cwd']
    assert ('--env-file' in args) == bool(environment)
    assert args[-6:] == ('-f', '/opt/old.yaml', '-f', str(Path('/opt/new.json')), 'config', '--quiet')


def config():
    return dict(name='existing', services={'api': dict(image='old', build={'context': '/old'},
        environment={'SECRET': 'fixture'}, volumes=[{'source': '/existing', 'target': '/data', 'read_only': True}],
        command=['uvicorn', 'existing'])}, networks={'business': {}})


def test_overlay_allows_only_image_and_build_changes():
    old, new = config(), config()
    new['services']['api'].update(image='sha256:tested', build={'context': '/new'})
    m.same_settings(old, new, ['api'])
    for field, value in (('environment', {'SECRET': 'different'}), ('volumes', []), ('command', ['new'])):
        changed = copy.deepcopy(new)
        changed['services']['api'][field] = value
        with pytest.raises(AssertionError, match='other than image/build'):
            m.same_settings(old, changed, ['api'])
    new['networks']['extra'] = {}
    with pytest.raises(AssertionError):
        m.same_settings(old, new, ['api'])


def test_shared_asset_collisions_fail_before_publish_but_index_may_change(tmp_path, monkeypatch):
    source, app = tmp_path / 'source', tmp_path / 'app'
    for root in (source, app):
        (root / 'frontend/dist/assets').mkdir(parents=True)
        (root / 'frontend/dist/assets/shared.js').write_text('same')
        (root / 'frontend/dist/index.html').write_text(root.name)
    monkeypatch.setattr(m, 'APP', app)
    m.assets_safe(source)
    (source / 'frontend/dist/assets/shared.js').write_text('new')
    with pytest.raises(AssertionError, match='collision'):
        m.assets_safe(source)


def test_native_dependency_drift_refused_before_creating_target(tmp_path):
    source, old = tmp_path / 'source/backend', tmp_path / 'old'
    source.mkdir(parents=True)
    old.mkdir()
    (source / 'pyproject.toml').write_text('changed')
    (old / 'pyproject.toml').write_text('old')
    with pytest.raises(AssertionError, match='dependency drift'):
        m.prepare_domestic_native(source.parent, 'fixture', old)


def test_backup_restore_is_unnetworked_and_cleanup_only_created_container(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(b.m, 'live', lambda name: {'Image': 'sha256:pinned-postgres'})
    monkeypatch.setattr(b.m, 'run', lambda *args, **kwargs: calls.append(args) or '')
    monkeypatch.setattr(b.subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(returncode=0))
    monkeypatch.setattr(b, 'fingerprint', lambda db: {'users': '28:hash'})
    dump = tmp_path / 'domestic.dump'
    dump.write_bytes(b'fixture')
    b.restore_check(('existing-production-db', 'hengxin', 'hengxin'), dump, {'users': '28:hash'}, 'overseas-fixture', 'domestic')
    assert '--network' in calls[0] and calls[0][calls[0].index('--network') + 1] == 'none'
    assert '--mount' in calls[0] and calls[0][-1] == 'sha256:pinned-postgres'
    assert calls[-1] == ('docker', 'rm', '-f', '-v', 'hx-member-restore-fixture-domestic')
    assert not any('existing-production-db' in call for call in calls)


def test_restore_create_failure_never_removes_preexisting_container(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(b.m, 'live', lambda name: {'Image': 'postgres'})
    def fail(*args, **kwargs):
        calls.append(args)
        raise RuntimeError('name already exists')
    monkeypatch.setattr(b.m, 'run', fail)
    with pytest.raises(RuntimeError, match='already exists'):
        b.restore_check(('production', 'user', 'db'), tmp_path / 'dump', {}, 'fixture', 'domestic')
    assert len(calls) == 1 and 'rm' not in calls[0]


def test_resource_verification_refuses_recreated_identity_redis(monkeypatch):
    data = {group: {'ids': {}} for group in m.GROUPS}
    data['identity']['ids']['hengxin-identity-identity-redis-1'] = 'original'
    monkeypatch.setattr(v.m, 'live', lambda name: {'Id': 'replacement', 'State': {'Running': True}})
    with pytest.raises(AssertionError, match='resource recreated'):
        v.resources_unchanged(data)
