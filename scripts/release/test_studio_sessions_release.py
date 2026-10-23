"""Release safety regression tests; never connect to production."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def release(monkeypatch):
    module = load('overseas-studio-sessions-deploy')
    # Production private-file permissions are POSIX-only, already covered by the
    # shared runtime tests. Keep these orchestration tests runnable on Windows.
    monkeypatch.setattr(module.m, 'private', save)
    return module


def save(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body if isinstance(body, str) else json.dumps(body), encoding='utf-8')


def test_package_keeps_review_clean_tree_and_full_backend_requirements():
    package = load('package-studio-sessions')
    assert package.p.VERSION == '0.2.50'
    assert package.p.DOMESTIC_MIGRATION == '0032'
    assert package.p.OVERSEAS_MIGRATION == 'overseas_0021'
    assert 'package-studio-sessions.py' in package.p.PACKAGING_HELPERS
    assert package.selected('hengxin-smart-image/backend/app/overseas/studio/image_recovery.py') == 'backend/app/overseas/studio/image_recovery.py'
    assert package.selected('scripts/release/overseas-studio-sessions-data.py') == 'scripts/release/overseas-studio-sessions-data.py'
    assert package.selected('hengxin-smart-image/backend/.env') is None
    with pytest.raises(ValueError, match='Commit all'):
        package.p.require_clean_tracked(lambda *args: b' M AGENTS.md')


def test_hook_graph_uses_new_schema_and_preserves_verified_backup(release):
    assert release.d.prepare is release.prepare
    assert release.a.schemas is release.schemas
    assert release.d.before_switch is release.migrate
    assert release.d.deploy is release.deploy
    assert release.d.evidence is release.evidence
    assert release.u.backup is release.a.a.backup
    assert release.a.OVERSEAS_PATHS[release.u.UNITS[0]] != release.a.OVERSEAS_PATHS[release.u.UNITS[1]]
    assert release.u.DROP > 'zzzzzzzzz-studio-delivery-20261023.conf'


def test_overlay_retains_full_environment_and_rejects_grant_loss(release):
    before = {'services': {'api': {'image': 'old', 'build': {}, 'mem_limit': release.d.resources.API_MEMORY,
        'restart': 'unless-stopped', 'environment': {'SECRET': 'opaque', release.OWNER_KEY: 'owner',
        release.GRANT_KEY: '["member"]', 'LEGACY_OWNER': 'unchanged'}}}}
    after = copy.deepcopy(before)
    after['services']['api'].update(release.d.resources.overlay(Path('/source'), 'new')['services']['api'])
    release.d.resources.same_settings(before, after, release.m)
    after['services']['api']['environment'][release.GRANT_KEY] = '[]'
    with pytest.raises(AssertionError, match='Compose changed'):
        release.d.resources.same_settings(before, after, release.m)


@pytest.mark.parametrize('members', ['[]', '{}', '["invalid"]', '["00000000-0000-0000-0000-000000000000"]'])
def test_existing_binding_validation_rejects_missing_grant(release, monkeypatch, members):
    monkeypatch.setattr(release.m, 'live', lambda _: {'Config': {'Env': [
        release.OWNER_KEY + '=10000000-0000-0000-0000-000000000001', release.GRANT_KEY + '=' + members]}})
    with pytest.raises((AssertionError, ValueError)):
        release.bindings()


def test_native_dependency_checks_each_baseline_before_install(release, monkeypatch, tmp_path):
    roots = [tmp_path / 'worker', tmp_path / 'outbox']
    source = tmp_path / 'src'
    for path in [source / 'backend', *roots]:
        for name in ('pyproject.toml', 'uv.lock'):
            save(path / name, 'same')
    monkeypatch.setattr(release.a, 'OVERSEAS_PATHS', dict(zip(release.u.UNITS, roots)))
    called = []
    monkeypatch.setattr(release, '_prepare_native', lambda *args: called.append(args) or 'installed')
    assert release.prepare_native(source, 'release') == 'installed'
    save(roots[1] / 'uv.lock', 'drift')
    with pytest.raises(AssertionError, match='dependency drift'):
        release.prepare_native(source, 'release')
    assert len(called) == 1


def test_install_receipt_binds_image_manifest_and_actual_directory(release, tmp_path):
    source = tmp_path / 'src'
    save(source / 'release.json', {'release': 'approved'})
    first = release.receipt(tmp_path, source, 'image1', tmp_path / 'native')
    assert first != release.receipt(tmp_path, source, 'image2', tmp_path / 'native')
    assert first != release.receipt(tmp_path, source, 'image1', tmp_path / 'different')
    save(source / 'release.json', {'release': 'drift'})
    assert first != release.receipt(tmp_path, source, 'image1', tmp_path / 'native')


def test_deploy_refuses_missing_or_changed_install_receipt_before_cutover(release, monkeypatch, tmp_path):
    source = tmp_path / 'src'
    save(source / 'release.json', '{}')
    save(tmp_path / 'native-target', '/installed/backend')
    save(tmp_path / 'NATIVE_INSTALL_TESTS.json', {'image': 'different'})
    monkeypatch.setattr(release.m, 'image_id', lambda *args: 'image')
    monkeypatch.setattr(release, '_deploy', lambda *args: pytest.fail('must not cut over'))
    with pytest.raises(AssertionError, match='receipt drift'):
        release.deploy(tmp_path, source, {}, 'tag')


def test_native_tests_use_actual_installed_source_no_live_env_or_data(release, monkeypatch, tmp_path):
    source = tmp_path / 'src'
    save(source / 'release.json', '{}')
    calls = []
    monkeypatch.setattr(release.subprocess, 'run', lambda args, **kwargs: calls.append((args, kwargs)))
    release.native_install_test(tmp_path, source, {}, 'sha256:image', Path('/installed/backend'))
    args, options = calls[0]
    assert args[args.index('--network') + 1] == 'none'
    assert args[args.index('--mount') + 1] == 'type=bind,src=' + str(Path('/installed/backend')) + ',dst=/installed,readonly'
    assert args[args.index('--entrypoint') + 1] == '/app/.venv/bin/python'
    assert args[args.index('--workdir') + 1] == '/installed'
    assert 'PYTHONPATH=/installed' in args
    assert '--env-file' not in args and '--privileged' not in args
    assert options['check'] and options['timeout'] == 600
    assert json.loads((tmp_path / 'NATIVE_INSTALL_TESTS.json').read_text())['image'] == 'sha256:image'


def test_migration_requires_restore_verified_backup_and_drain(release, tmp_path):
    with pytest.raises(AssertionError, match='backup missing'):
        release.migrate(tmp_path, tmp_path / 'src', 'image', {}, tmp_path / 'backup')
    save(tmp_path / 'backup/COMPLETE', 'verified')
    with pytest.raises(AssertionError, match='not drained'):
        release.migrate(tmp_path, tmp_path / 'src', 'image', {}, tmp_path / 'backup')


def test_migration_rejects_data_drift_before_mutating_schema(release, monkeypatch, tmp_path):
    save(tmp_path / 'backup/COMPLETE', 'verified')
    save(tmp_path / 'EXECUTORS_STOPPED', 'drained')
    save(tmp_path / 'backup/fingerprints.json', {'business': 'old'})
    monkeypatch.setattr(release, 'schemas', lambda: None)
    monkeypatch.setattr(release.a.a, 'fingerprint', lambda _: {'business': 'changed'})
    monkeypatch.setattr(release.m, 'compose', lambda *a, **k: pytest.fail('must not migrate'))
    with pytest.raises(AssertionError, match='Data drift'):
        release.migrate(tmp_path, tmp_path / 'src', 'image', {}, tmp_path / 'backup')
    assert not (tmp_path / 'MIGRATION_STARTED').exists()


def test_projection_removes_only_explicitly_added_columns(release):
    statements = []
    def sql(query):
        statements.append(query)
        if query.startswith('SELECT tablename'):
            return '\n'.join(['overseas_alembic_version', 'overseas_studio_conversations',
                'overseas_studio_pictures', 'overseas_members', release.data_check.TABLE])
        return '1:hash'
    result = release.data_check.original_rows(sql)
    assert set(result) == {'overseas_studio_conversations', 'overseas_studio_pictures', 'overseas_members'}
    conversation = next(q for q in statements if 'FROM public."overseas_studio_conversations"' in q)
    assert "-'name'-'version'" in conversation and "-'id'" not in conversation
    picture = next(q for q in statements if 'FROM public."overseas_studio_pictures"' in q)
    assert "-'origin_turn_id'" in picture and "-'turn_id'" not in picture
    member = next(q for q in statements if 'FROM public."overseas_members"' in q)
    assert "-'" not in member


def test_column_projection_allows_only_declared_new_fields_and_picture_nullability(release):
    original = [{'table_name': 'overseas_studio_pictures', 'column_name': 'turn_id', 'is_nullable': 'NO'},
                {'table_name': 'overseas_members', 'column_name': 'name', 'is_nullable': 'NO'}]
    migrated = copy.deepcopy(original)
    migrated[0]['is_nullable'] = 'YES'
    migrated.append({'table_name': 'overseas_studio_conversations', 'column_name': 'name'})
    assert release.data_check.original_columns(original) == release.data_check.original_columns(migrated)
    migrated[1]['is_nullable'] = 'YES'
    assert release.data_check.original_columns(original) != release.data_check.original_columns(migrated)


@pytest.mark.parametrize('name', ['bad";DROP TABLE x', 'name.with.dot', '../outside'])
def test_projection_refuses_sql_identifier_injection(release, name):
    with pytest.raises(AssertionError, match='Unsafe SQL'):
        release.data_check.identifier(name)


def test_drain_requires_two_stable_checks_and_bounds_every_probe(release, monkeypatch, tmp_path):
    elapsed, timeouts = [0], []
    monkeypatch.setattr(release.time, 'monotonic', lambda: elapsed[0])
    monkeypatch.setattr(release.time, 'sleep', lambda seconds: elapsed.__setitem__(0, elapsed[0] + seconds))
    monkeypatch.setattr(release.d.drain, 'idle', lambda _: True)
    monkeypatch.setattr(release, 'evidence', lambda work, timeout: timeouts.append(timeout) or
                        {'workers': {}, 'jobs': 0, 'deleting': 0})
    release.wait_empty(tmp_path, 'probe', timeout=10)
    assert timeouts == [10, 7]
    assert (tmp_path / 'probe.json').is_file()


def test_busy_drain_deadline_does_not_stop_any_service(release, monkeypatch, tmp_path):
    elapsed = [0]
    monkeypatch.setattr(release.time, 'monotonic', lambda: elapsed[0])
    monkeypatch.setattr(release.time, 'sleep', lambda seconds: elapsed.__setitem__(0, elapsed[0] + seconds))
    monkeypatch.setattr(release.d.drain, 'idle', lambda _: False)
    monkeypatch.setattr(release.m, 'run', lambda *a, **k: pytest.fail('must not stop services'))
    monkeypatch.setattr(release, 'evidence', lambda *a, **k: {'workers': {}, 'jobs': 1, 'deleting': 0})
    with pytest.raises(AssertionError, match='deadline reached'):
        release.wait_empty(tmp_path, 'busy', timeout=5)


def test_migration_verifier_rejects_original_value_loss(release, monkeypatch):
    helper = release.data_check
    monkeypatch.setattr(helper, 'tables', lambda _: ['old', helper.TABLE])
    monkeypatch.setattr(helper, 'columns', lambda _: [])
    monkeypatch.setattr(helper, 'original_rows', lambda _: {'old': 'lost-row'})
    with pytest.raises(AssertionError, match='Original business data changed'):
        helper.verify(lambda _: pytest.fail('must fail before backfill checks'),
                      {'tables': ['old'], 'columns': [], 'rows': {'old': 'original'}})


@pytest.mark.parametrize('fault, expected', [
    (None, None),
    ('overseas_studio_uploads', 'Historical ownership'),
    ('overseas_task_requests', 'Historical ownership'),
    ('origin_turn_id', 'Historical ownership'),
    ('scope IS DISTINCT', 'Historical visibility'),
    ('WITH numbered', 'Conversation names/version'),
    ('LEFT JOIN overseas_studio_pictures', 'Archive source snapshot'),
])
def test_added_values_checked_separately_from_original_rows(release, monkeypatch, fault, expected):
    helper = release.data_check
    original = [{'table_name': 'overseas_studio_pictures', 'column_name': 'turn_id', 'is_nullable': 'YES'}]
    fields = original + [{'table_name': table, 'column_name': name}
                         for table, names in helper.ADDED.items() for name in names]
    monkeypatch.setattr(helper, 'tables', lambda _: ['old', helper.TABLE])
    monkeypatch.setattr(helper, 'columns', lambda _: fields)
    monkeypatch.setattr(helper, 'original_rows', lambda _: {'old': 'unchanged'})
    baseline = {'tables': ['old'], 'columns': original, 'rows': {'old': 'unchanged'}}
    def sql(query):
        if fault and fault in query:
            return '1'
        return '1' if "='UNIQUE (task_id, checksum, scope)'" in query else '0'
    if expected:
        with pytest.raises(AssertionError, match=expected):
            helper.verify(sql, baseline)
    else:
        helper.verify(sql, baseline)


def test_package_rejects_sessions_preview_entry(monkeypatch):
    package = load('package-studio-sessions')
    monkeypatch.setattr(package, '_validate', lambda _: None)
    package.validate({'frontend/dist/index.html': b'production'})
    with pytest.raises(ValueError, match='Preview entry'):
        package.validate({'frontend/dist/preview-studio-sessions.html': b'preview'})
