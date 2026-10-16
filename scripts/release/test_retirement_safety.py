import importlib.util
import json
from pathlib import Path
import subprocess

import pytest


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


b, n, p, d = (load(name) for name in ('retirement-backup', 'retirement-native', 'package-retirement', 'retirement-drain'))


def test_preserved_rows_and_table_set_are_exact():
    before = {'api_image_tasks': '1:hash', 'users': '3:users'}
    b.compare(before, dict(before))
    for after in ({'api_image_tasks': '0:empty', 'users': '3:users'},
                  {**before, 'skills': '4:skills'}, {'users': '3:users'}):
        with pytest.raises(AssertionError):
            b.compare(before, after)


def test_restore_fingerprint_is_raw_but_migration_projection_is_explicit(monkeypatch):
    statements = []

    def query(_database, sql):
        statements.append(sql)
        return 'alembic_version\njob_records\nskills\nsystem_settings' if 'pg_tables' in sql else 'hash'

    monkeypatch.setattr(b.b, 'query', query)
    raw = b.fingerprint(None)
    assert set(raw) == {'job_records', 'skills', 'system_settings'}
    assert not any('kind NOT IN' in sql for sql in statements)
    policy = dict(drop_tables=['skills'], row_filters={'job_records': "kind NOT IN ('skill_sync')"},
                  json_remove={'system_settings': {'values': ['defaultSkillIds']}})
    statements.clear()
    projected = b.fingerprint(None, policy)
    assert set(projected) == {'job_records', 'system_settings'}
    assert any("kind NOT IN ('skill_sync')" in sql for sql in statements)
    assert any('jsonb_build_object' in sql and 'defaultSkillIds' in sql for sql in statements)


def test_after_verification_cannot_hide_surviving_retired_rows(monkeypatch, tmp_path):
    (tmp_path / 'contract.json').write_text(json.dumps({'drop_tables': ['skills']}))
    (tmp_path / 'fingerprints-preserved.json').write_text(json.dumps({'job_records': '27:api'}))
    calls = []

    def fingerprint(database, policy=None):
        calls.append(policy)
        return {'job_records': '34:api-and-old'}

    monkeypatch.setattr(b, 'fingerprint', fingerprint)
    with pytest.raises(AssertionError, match='job_records'):
        b.verify_after(tmp_path)
    assert calls == [None]


def test_contract_is_literal_not_executed(tmp_path):
    file = tmp_path / 'backend/migrations/versions/0030_retire_legacy.py'
    file.parent.mkdir(parents=True)
    contract = dict(version=1, drop_tables=['table_' + str(i) for i in range(22)],
                    retired_job_kinds=['generation', 'skill_install', 'skill_check', 'skill_sync'],
                    row_filters={}, drop_columns={}, json_remove={})
    file.write_text('raise RuntimeError("Do not import migration")\nRETIREMENT_CONTRACT = ' + repr(contract))
    assert b.contract(tmp_path) == contract
    file.write_text('RETIREMENT_CONTRACT = dict(version=1)')
    with pytest.raises(ValueError):
        b.contract(tmp_path)


def test_native_shared_venv_shebang_is_replaced_with_prepared_interpreter():
    old = dict(cwd='/opt/hengxin-native-releases/domestic-old/backend', argv=[
        '/opt/hengxin-native-releases/overseas-old/backend/.venv/bin/python',
        '/opt/hengxin-native-releases/domestic-old/backend/.venv/bin/celery',
        '-A', 'app.worker.celery_app:celery_app', 'worker', '--concurrency=5'])
    target = '/opt/hengxin-native-releases/domestic-retire-20261016-abcdef0/backend'
    result = n.render(old, target)
    assert 'overseas-old' not in result and 'domestic-old' not in result
    assert target + '/.venv/bin/python' in result and target + '/.venv/bin/celery' in result
    assert '--concurrency=5' in result
    with pytest.raises(AssertionError):
        n.render(old, target + '\nExecStart=/malicious')


def test_cleanup_unknown_state_never_stops_any_process(monkeypatch):
    calls = []

    def run(*args, **kwargs):
        calls.append(args)
        raise subprocess.TimeoutExpired(args, 1)

    monkeypatch.setattr(d.m, 'run', run)
    with pytest.raises(subprocess.TimeoutExpired):
        d.cleanup_idle(timeout=1)
    assert calls and all(args[0] == 'docker' for args in calls)


def test_cleanup_pending_blocks_under_one_deadline(monkeypatch):
    moments = iter((0, 0, 0, 2))
    monkeypatch.setattr(d.time, 'monotonic', lambda: next(moments))
    monkeypatch.setattr(d.time, 'sleep', lambda _: None)
    monkeypatch.setattr(d.m, 'run', lambda *_, **kw: '1')
    with pytest.raises(AssertionError, match='pending'):
        d.cleanup_idle(timeout=1)


def test_package_rejects_retired_code_and_old_version():
    files = {name: b'' for name in p.REQUIRED}
    files['frontend/package.json'] = b'{"version":"0.2.40"}'
    files['frontend/dist/index.html'] = b'<script src="/assets/main.js"></script>'
    files['frontend/dist/assets/main.js'] = b'console.log(1)'
    p.validate(files)
    with pytest.raises(ValueError, match='Retired'):
        p.validate({**files, 'backend/app/modules/tasks/models.py': b''})
    with pytest.raises(ValueError, match='version'):
        p.validate({**files, 'frontend/package.json': b'{"version":"0.2.39"}'})
    assert p.p.RELEASE_PREFIX == 'domestic-retire-20261016-'
    assert p.p.DOMESTIC_MIGRATION == '0030' and p.p.OVERSEAS_MIGRATION == 'overseas_0017'


def test_package_dirty_source_refused_before_review(monkeypatch, tmp_path):
    monkeypatch.setattr(p.p.m.common, 'git', lambda *_: b' M changed.py')
    monkeypatch.setattr(p.p.m.common, 'reviewed_status', lambda *_: pytest.fail('uncommitted'))
    with pytest.raises(ValueError, match='Commit all tracked'):
        p.build(tmp_path)


def test_release_name_accepted_by_shared_ledger():
    ledger = load('release-retention-state')
    assert ledger.RELEASE.fullmatch('domestic-retire-20261016-abcdef0')


def test_live_source_privacy_scan():
    root = Path(__file__).resolve().parents[2]
    for name in p.SCRIPTS:
        path = root / 'scripts/release' / name
        p.p.m.common.privacy_check('scripts/release/' + name, path.read_bytes())


def test_cleanup_startup_requires_real_success_and_rejects_error_logs():
    v = load('retirement-verify')
    assert not v.completed('[]\n', True)
    assert v.completed('[]\n[]\n', True)
    assert v.completed('{"status":"completed","resources":[],"objectsRemoved":0}', False)
    assert not v.completed('Started Hengxin retention\n', False)
    for body in ('{"status":"unavailable"}', 'Traceback: broken import',
                 '{"status":"disabled"}',
                 '{"status":"completed","resources":[{"status":"retry"}],"objectsRemoved":0}'):
        with pytest.raises(AssertionError):
            v.completed(body, False)


def test_cleanup_uses_deleted_receipt_status_not_completed_phase():
    assert "status != 'deleted'" in d.CLEANUP
    assert "status != 'completed'" not in d.CLEANUP


def test_actual_migration_contract_can_be_read_without_app_import():
    source = Path(__file__).resolve().parents[2] / 'hengxin-smart-image'
    policy = b.contract(source)
    assert len(policy['drop_tables']) == 22
    assert 'api_image_tasks' not in policy['drop_tables']
