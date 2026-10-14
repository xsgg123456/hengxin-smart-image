import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

spec = importlib.util.spec_from_file_location('studio_runtime_test', Path(__file__).with_name('native-studio-runtime.py'))
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


@pytest.mark.parametrize('target', ['frontend/package.json', 'OVERSEAS_RELEASE.json'])
@pytest.mark.parametrize('version', ['0.2.30', '0.2.32'])
def test_wrong_previous_version_rejected(tmp_path, monkeypatch, target, version):
    monkeypatch.setattr(s.m, 'APP', tmp_path)
    (tmp_path / 'frontend').mkdir()
    (tmp_path / 'frontend/package.json').write_text(json.dumps({'version': s.PREVIOUS}))
    (tmp_path / 'OVERSEAS_RELEASE.json').write_text(json.dumps({'frontendVersion': s.PREVIOUS}))
    s.previous_version()
    (tmp_path / target).write_text(json.dumps({'version': version, 'frontendVersion': version}))
    with pytest.raises(AssertionError, match='drift'):
        s.previous_version()


@pytest.mark.parametrize('domestic,overseas', [('0027', s.OLD_SCHEMA), ('0028', 'overseas_0013'), ('0028', s.NEW_SCHEMA)])
def test_exact_old_schemas_required(monkeypatch, domestic, overseas):
    monkeypatch.setattr(s.r, 'sql', lambda _: domestic)
    monkeypatch.setattr(s.u, 'sql', lambda _: overseas)
    with pytest.raises(AssertionError, match='schema drift'):
        s.schemas(s.OLD_SCHEMA)


def test_approved_image_compared_to_installed_image(tmp_path, monkeypatch):
    (tmp_path / 'INSTALL_TEST_IMAGE_ID').write_text('sha256:installed')
    monkeypatch.setattr(s.m, 'run', lambda *a, **kw: 'sha256:changed')
    with pytest.raises(AssertionError):
        s.m.image_id(tmp_path, 'image')


def test_overlay_pins_both_api_and_migration_to_tested_identity(tmp_path):
    config = s.overlay(tmp_path, 'sha256:tested')
    assert set(config['services']) == {'api', 'migrate'}
    assert all(service['image'] == 'sha256:tested' for service in config['services'].values())


def test_failure_records_unavailable_schema_and_failed_closure(tmp_path, monkeypatch):
    monkeypatch.setattr(s.h, 'close_edge', Mock(side_effect=RuntimeError('close')))
    monkeypatch.setattr(s.m, 'compose', Mock(side_effect=RuntimeError('stop')))
    monkeypatch.setattr(s.r, 'sql', Mock(side_effect=RuntimeError('db')))
    monkeypatch.setattr(s.u, 'sql', Mock(return_value=s.NEW_SCHEMA))
    monkeypatch.setattr(s.m, 'private', lambda path, data: path.write_text(json.dumps(data)))
    s.failure(tmp_path, 'migration', ValueError('initial failure'), 'edge', {'overseas': {}})
    report = json.loads((tmp_path / 'FAILURE.json').read_text())
    assert report['errorType'] == 'ValueError'
    assert report['edgeClosed'] is report['apiStopped'] is False
    assert report['domesticSchema'] == 'unavailable:RuntimeError'
    assert report['overseasSchema'] == s.NEW_SCHEMA


def test_validate_target_manifest_and_hashes(tmp_path, monkeypatch):
    source = tmp_path / 'src'
    (source / 'frontend').mkdir(parents=True)
    manifest = dict(release='fixture', frontendVersion=s.VERSION, migration='0028', overseasMigration=s.NEW_SCHEMA)
    (source / 'release.json').write_text(json.dumps(manifest))
    (source / 'frontend/package.json').write_text(json.dumps({'version': s.VERSION}))
    hashes = Mock()
    monkeypatch.setattr(s.r, 'hashes', hashes)
    assert s.validate(tmp_path, 'fixture')[0] == source
    hashes.assert_called_once_with(source, manifest)
    manifest['overseasMigration'] = s.OLD_SCHEMA
    (source / 'release.json').write_text(json.dumps(manifest))
    with pytest.raises(AssertionError):
        s.validate(tmp_path, 'fixture')
