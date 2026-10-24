"""Offline release guard regressions; no production tools or configuration."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), Path(__file__).with_name(name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def save(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body if isinstance(body, str) else json.dumps(body), encoding='utf-8')


@pytest.fixture
def release(monkeypatch):
    result = load('studio-delivery-reliability-20261024')
    monkeypatch.setattr(result.m, 'private', save)
    return result


def test_package_reuses_reviewed_clean_source_gate_and_private_file_exclusion():
    package = load('package-studio-delivery-reliability')
    assert package.p.VERSION == '0.2.51'
    assert package.p.DOMESTIC_MIGRATION == '0032'
    assert package.p.OVERSEAS_MIGRATION == 'overseas_0021'
    assert 'package-studio-delivery-reliability.py' in package.p.PACKAGING_HELPERS
    assert package.selected(package.ENTRY) == package.ENTRY
    assert all(package.selected(path) == path and path in package.p.REQUIRED for path in package.HELPERS)
    assert package.selected('scripts/release/delivery-repair-request.private.json') is None
    assert package.selected('hengxin-smart-image/backend/.env') is None
    assert package.selected('output/studio-delivery-reliability-20261024/original-eight.json') is None
    with pytest.raises(ValueError, match='Commit all'):
        package.p.require_clean_tracked(lambda *args: b' M AGENTS.md')


def test_adapter_uses_current_verified_baseline_and_full_release_hooks(release):
    assert release.d.TARGET_VERSION == '0.2.51'
    assert release.d.BASE_VERSION == '0.2.50'
    assert release.a.BASE_RELEASE == 'overseas-20261024-71ed440'
    assert len(set(release.a.OVERSEAS_PATHS.values())) == 1
    assert release.d.before_switch is release.before_switch
    assert release.d.prepare is release.prepare
    assert release.d.installed is release.installed
    assert release.d.deploy is release.deploy
    assert release.u.backup is release.a.a.backup
    assert release.d.evidence is release.s.evidence
    assert release.d.wait_empty is release.s.wait_empty
    assert release.u.DROP > 'zzzzzzzzzz-studio-sessions-20261024.conf'


def test_adapter_load_does_not_import_original_repair_tools(monkeypatch):
    original = importlib.util.spec_from_file_location

    def without_repair(name, location, *args, **kwargs):
        assert Path(location).name not in {
            'studio-delivery-release-repair.py', 'studio-delivery-repair-runtime.py'
        }, 'Normal release must not load original-image repair tools'
        return original(name, location, *args, **kwargs)

    monkeypatch.setattr(importlib.util, 'spec_from_file_location', without_repair)
    load('studio-delivery-reliability-20261024')


@pytest.mark.parametrize('request_state', ['absent', 'stale'])
def test_prepare_preserves_skill_guard_without_original_repair_request(release, monkeypatch, tmp_path, request_state):
    request = tmp_path / 'delivery-repair-request.private.json'
    if request_state == 'stale':
        save(request, 'deleted task; not a valid restoration request')
    events = []
    source, manifest = tmp_path / 'src', {'files': {}}
    monkeypatch.setattr(release, 'preflight', lambda: events.append('preflight'))
    monkeypatch.setattr(release, 'skill_states', lambda: '[{"enabled":false}]')

    def inherited(*args):
        assert args == (tmp_path, source, manifest, 'image')
        assert (tmp_path / 'delivery-skill-states.private.json').read_text() == '[{"enabled":false}]'
        events.append('prepare')

    monkeypatch.setattr(release, '_prepare', inherited)
    release.prepare(tmp_path, source, manifest, 'image')
    assert events == ['preflight', 'prepare']
    assert not list(tmp_path.glob('DELIVERY_REPAIR_*'))
    assert request.exists() is (request_state == 'stale')
    if request.exists():
        assert request.read_text() == 'deleted task; not a valid restoration request'


@pytest.mark.parametrize('failure', ['preflight', 'skills'])
def test_prepare_still_blocks_baseline_or_skill_drift(release, monkeypatch, tmp_path, failure):
    def preflight():
        if failure == 'preflight':
            raise AssertionError('API image baseline drift')

    save(tmp_path / 'delivery-skill-states.private.json', 'original')
    monkeypatch.setattr(release, 'preflight', preflight)
    monkeypatch.setattr(release, 'skill_states', lambda: 'changed')
    monkeypatch.setattr(release, '_prepare', lambda *a: pytest.fail('Drift must block inherited preparation'))
    with pytest.raises(AssertionError, match='drift'):
        release.prepare(tmp_path, tmp_path / 'src', {}, 'image')
    assert (tmp_path / 'delivery-skill-states.private.json').read_text() == 'original'


def test_installed_still_requires_inherited_verification(release, monkeypatch, tmp_path):
    def failed(*args):
        raise AssertionError('Installed source hash drift')

    monkeypatch.setattr(release, '_installed', failed)
    monkeypatch.setattr(release, 'skill_states', lambda: pytest.fail('Inherited verification must run first'))
    with pytest.raises(AssertionError, match='source hash drift'):
        release.installed(tmp_path, {}, 'image', {}, {}, Path('/installed/backend'))
    assert not (tmp_path / 'DELIVERY_PRESERVATION_VERIFIED').exists()


def test_no_migration_cutover_requires_verified_backup_and_stopped_executors(release, tmp_path):
    with pytest.raises(AssertionError, match='backup missing'):
        release.before_switch(tmp_path, tmp_path / 'src', 'image', {}, tmp_path / 'backup')
    save(tmp_path / 'backup/COMPLETE', 'verified')
    with pytest.raises(AssertionError, match='not drained'):
        release.before_switch(tmp_path, tmp_path / 'src', 'image', {}, tmp_path / 'backup')


@pytest.mark.parametrize('drift', ['none', 'rows', 'skills'])
def test_no_migration_hook_proves_data_and_skill_states_without_writes(release, monkeypatch, tmp_path, drift):
    save(tmp_path / 'backup/COMPLETE', 'verified')
    save(tmp_path / 'EXECUTORS_STOPPED', 'drained')
    save(tmp_path / 'backup/fingerprints.json', {'rows': 'original'})
    save(tmp_path / 'delivery-skill-states.private.json', 'original')
    monkeypatch.setattr(release, 'schemas', lambda: None)
    monkeypatch.setattr(release.a.a, 'fingerprint', lambda _: {'rows': 'changed' if drift == 'rows' else 'original'})
    monkeypatch.setattr(release, 'skill_states', lambda: 'changed' if drift == 'skills' else 'original')
    monkeypatch.setattr(release.m, 'compose', lambda *a, **k: pytest.fail('must not migrate'))
    if drift == 'none':
        release.before_switch(tmp_path, tmp_path / 'src', 'image', {}, tmp_path / 'backup')
        assert (tmp_path / 'SCHEMA_UNCHANGED').is_file()
    else:
        with pytest.raises(AssertionError, match='drift'):
            release.before_switch(tmp_path, tmp_path / 'src', 'image', {}, tmp_path / 'backup')
        assert not (tmp_path / 'SCHEMA_UNCHANGED').exists()
    assert not (tmp_path / 'MIGRATION_STARTED').exists()


def test_preservation_rejects_skill_changes_across_prepare_retries(release, monkeypatch, tmp_path):
    monkeypatch.setattr(release, 'skill_states', lambda: '[{"enabled":false}]')
    release.preserve_skill_states(tmp_path)
    release.preserve_skill_states(tmp_path)
    monkeypatch.setattr(release, 'skill_states', lambda: '[{"enabled":true}]')
    with pytest.raises(AssertionError, match='Skill states drift'):
        release.preserve_skill_states(tmp_path)


def test_full_compose_environment_preserved_including_permissions(release):
    before = {'services': {'api': {'image': 'old', 'build': {}, 'mem_limit': release.d.resources.API_MEMORY,
        'restart': 'unless-stopped', 'environment': {'EXISTING': 'opaque', release.s.OWNER_KEY: 'owner',
        release.s.GRANT_KEY: '["member"]'}}}}
    after = copy.deepcopy(before)
    after['services']['api'].update(release.d.resources.overlay(Path('/source'), 'new')['services']['api'])
    release.d.resources.same_settings(before, after, release.m)
    del after['services']['api']['environment'][release.s.GRANT_KEY]
    with pytest.raises(AssertionError, match='Compose changed'):
        release.d.resources.same_settings(before, after, release.m)


def test_native_tests_bind_actual_installed_files_and_discovered_fault_suites(release, monkeypatch, tmp_path):
    source, target = tmp_path / 'src', Path('/installed/backend')
    save(source / 'release.json', '{}')
    calls = []
    monkeypatch.setattr(release.subprocess, 'run', lambda args, **kw: calls.append((args, kw)))
    release.native_install_test(tmp_path, source, {'files': {'backend/tests/test_studio_delivery_snapshot.py': 'hash'}}, 'sha256:image', target)
    args, options = calls[0]
    assert args[args.index('--network') + 1] == 'none'
    assert args[args.index('--mount') + 1] == 'type=bind,src=' + str(target) + ',dst=/installed,readonly'
    assert args[args.index('--entrypoint') + 1] == '/app/.venv/bin/python'
    assert 'PYTHONPATH=/installed' in args and 'PYTHONDONTWRITEBYTECODE=1' in args
    assert 'tests/test_studio_delivery_snapshot.py' in args
    assert '--env-file' not in args and '--privileged' not in args
    assert options['check'] and options['timeout'] == 600
    assert json.loads((tmp_path / 'NATIVE_INSTALL_TESTS.json').read_text()) == release.s.receipt(tmp_path, source, 'sha256:image', target)


@pytest.mark.parametrize('changed', ['image', 'manifest', 'target'])
def test_cutover_refuses_install_receipt_drift(release, monkeypatch, tmp_path, changed):
    source = tmp_path / 'src'
    save(source / 'release.json', '{}')
    save(tmp_path / 'native-target', '/installed/backend')
    receipt = release.s.receipt(tmp_path, source, 'image', Path('/installed/backend'))
    receipt[changed] = 'changed'
    save(tmp_path / 'NATIVE_INSTALL_TESTS.json', receipt)
    monkeypatch.setattr(release.m, 'image_id', lambda *args: 'image')
    monkeypatch.setattr(release.s, '_deploy', lambda *a: pytest.fail('must not cut over'))
    with pytest.raises(AssertionError, match='receipt drift'):
        release.d.deploy(tmp_path, source, {}, 'tag')


def test_preflight_rejects_obsolete_grant_last_assumption_before_other_probes(release, monkeypatch, tmp_path):
    monkeypatch.setattr(release.m, 'APP', tmp_path)
    save(tmp_path / 'frontend/package.json', {'version': '0.2.50'})
    for name in ('FRONTEND_RELEASE.json', 'OVERSEAS_RELEASE.json'):
        save(tmp_path / name, {'release': release.a.BASE_RELEASE})
    live = {'Image': release.a.BASE_IMAGE, 'State': {'Running': True, 'Health': {'Status': 'healthy'}},
        'HostConfig': {'Memory': release.d.resources.API_MEMORY, 'RestartPolicy': {'Name': 'unless-stopped'}},
        'Config': {'Labels': {'com.docker.compose.project.config_files': release.s.GRANT_OVERLAY}}}
    monkeypatch.setattr(release.m, 'live', lambda _: live)
    monkeypatch.setattr(release.s, 'bindings', lambda: pytest.fail('must reject old topology first'))
    with pytest.raises(AssertionError, match='Compose chain drift'):
        release.preflight()
