import copy
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath

import pytest


def module(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


n = module('domestic-record-filters-native')
RELEASE = 'domestic-record-filters-20261022-abcdef0'
TARGET = '/opt/hengxin-native-releases/' + RELEASE + '/backend'


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value if isinstance(value, str) else json.dumps(value))


def rows():
    result = {}
    for index, unit in enumerate(n.UNITS):
        cwd = '/opt/hengxin-native-releases/previous-' + str(index) + '/backend'
        result[unit] = dict(pid=100 + index, cwd=cwd, files={},
            argv=[cwd + '/.venv/bin/python', '-m', 'app.worker.celery_app' if unit == n.UNIT else 'app.retention.worker', '--loop'],
            environment={'TOKEN': 'private-value', 'PWD': cwd, 'GENERATION_CONCURRENCY': '5'},
            policy={'User': 'codex', 'UMask': '0077', 'MemoryMax': '1234'})
    return result


def test_render_only_relocates_executable_and_cwd():
    for row in rows().values():
        text = n.render(row, TARGET)
        assert 'WorkingDirectory=' + TARGET in text
        assert '"' + TARGET + '/.venv/bin/python"' in text
        assert 'Environment' not in text and 'private-value' not in text and 'MemoryMax' not in text
        assert row['argv'][-1] == '--loop'
    with pytest.raises(AssertionError):
        n.render(rows()[n.UNIT], TARGET.replace('record-filters', 'retention'))


@pytest.mark.parametrize('unsafe', ['--value=$SECRET', '--percent=%u', 'with"quote', 'new\nline', 'new\rline', 'back\\slash'])
def test_render_rejects_systemd_expansion_and_injection(unsafe):
    row = rows()[n.UNIT]
    row['argv'].append(unsafe)
    with pytest.raises(AssertionError):
        n.render(row, TARGET)


@pytest.fixture
def native(tmp_path, monkeypatch):
    work, backup = tmp_path / 'work', tmp_path / 'backup'
    monkeypatch.setattr(n, 'SYSTEMD', tmp_path / 'systemd')
    monkeypatch.setattr(n.m, 'private', save)
    baseline = rows()
    for unit, row in baseline.items():
        path = n.SYSTEMD / (unit + '.service.d') / n.DROPIN
        save(path, 'old override ' + unit)
        row['files'][str(path)] = n.m.digest(path)
        save(work / (unit + '.conf'), n.render(row, TARGET))
    save(work / 'native-snapshots.private.json', baseline)
    save(work / 'native-target', TARGET)
    for name in ('NATIVE_PREPARED', 'EXECUTORS_STOPPED', 'CLEANUP_STOPPED'):
        save(work / name, 'yes')
    n.backup(backup, {'nativeOverrides': n.override_state()})
    save(backup / 'COMPLETE', 'yes')
    events = []
    monkeypatch.setattr(n.m, 'run', lambda *a, **kw: events.append(a))
    monkeypatch.setattr(n, 'show', lambda unit, key: '0' if key == 'MainPID' else TARGET)
    monkeypatch.setattr(n, 'code_hashes', lambda *_: events.append(('hashes',)))
    return work, backup, baseline, events


def test_switch_keeps_exact_original_dropin_bytes_and_only_updates_three(native):
    work, backup, baseline, events = native
    saved = json.loads((backup / 'native-overrides-before.private.json').read_text())
    n.switch(work, backup)
    assert events == [('hashes',), ('systemctl', 'daemon-reload')]
    for unit in n.UNITS:
        path = n.SYSTEMD / (unit + '.service.d') / n.DROPIN
        assert bytes.fromhex(saved[str(path)]['contentHex']) == ('old override ' + unit).encode()
        assert path.read_text() == n.render(baseline[unit], TARGET)


@pytest.mark.parametrize('marker', ['COMPLETE', 'NATIVE_PREPARED', 'EXECUTORS_STOPPED', 'CLEANUP_STOPPED'])
def test_switch_requires_backup_preparation_and_drained_markers(native, marker):
    work, backup, _, events = native
    (backup / marker if marker == 'COMPLETE' else work / marker).unlink()
    with pytest.raises(AssertionError):
        n.switch(work, backup)
    assert not events


def test_switch_checks_all_pids_before_writing_any_unit(native, monkeypatch):
    work, backup, _, events = native
    before = n.override_state()
    monkeypatch.setattr(n, 'show', lambda unit, key: '99' if unit == n.RETENTION else '0')
    with pytest.raises(AssertionError, match='still running'):
        n.switch(work, backup)
    assert n.override_state() == before and not events


@pytest.mark.parametrize('drift', ['override', 'prepared', 'policy'])
def test_switch_rejects_drift_before_any_service_write(native, drift):
    work, backup, baseline, events = native
    if drift == 'override':
        save(Path(next(iter(baseline[n.RETENTION]['files']))), 'changed')
    elif drift == 'prepared':
        save(work / (n.RETENTION + '.conf'), 'changed')
    else:
        path = work / 'environment.private'
        save(path, 'original')
        baseline[n.RETENTION]['files'][str(path)] = n.m.digest(path)
        save(work / 'native-snapshots.private.json', baseline)
        save(path, 'changed')
    before = n.override_state()
    with pytest.raises(AssertionError):
        n.switch(work, backup)
    assert n.override_state() == before and not events


def test_backup_records_absent_override_for_manual_recovery(tmp_path, monkeypatch):
    monkeypatch.setattr(n, 'SYSTEMD', tmp_path / 'systemd')
    monkeypatch.setattr(n.m, 'private', save)
    n.backup(tmp_path / 'backup', {'nativeOverrides': n.override_state()})
    saved = json.loads((tmp_path / 'backup/native-overrides-before.private.json').read_text())
    assert len(saved) == 3 and all(row == {'digest': None, 'contentHex': None} for row in saved.values())


@pytest.mark.parametrize('drift', [None, 'cwd', 'argv', 'environment', 'policy', 'files', 'pid'])
def test_verify_permits_only_relocation_and_transient_environment(native, monkeypatch, drift):
    work, _, before, events = native
    after = copy.deepcopy(before)
    for unit, row in after.items():
        row.update(pid=row['pid'] + 500, cwd=TARGET, argv=n.target_argv(before[unit], TARGET))
        row['environment'].update(PWD=TARGET, INVOCATION_ID='new')
        row['files'][str(n.SYSTEMD / (unit + '.service.d') / n.DROPIN)] = n.m.digest(work / (unit + '.conf'))
    if drift:
        row = after[n.DELETE]
        if drift in ('files', 'environment', 'policy'):
            row[drift]['unexpected'] = 'private-value'
        elif drift == 'argv':
            row[drift].append('--wrong')
        elif drift == 'pid':
            row['pid'] = before[n.DELETE]['pid']
        else:
            row['cwd'] = before[n.DELETE]['cwd']
    monkeypatch.setattr(n, 'snapshot', lambda unit: after[unit])
    monkeypatch.setattr(n.old, 'snapshot', lambda unit: after[unit])
    if drift:
        with pytest.raises(AssertionError) as error:
            n.verify(work)
        assert 'private-value' not in str(error.value)
    else:
        n.verify(work)
        assert events == [('hashes',)]


def test_native_hashes_include_both_shared_cleanup_modules_and_all_backend_files(tmp_path, monkeypatch):
    monkeypatch.setattr(n, 'NATIVE_ROOT', tmp_path / 'native')
    target = n.NATIVE_ROOT / RELEASE / 'backend'
    save(tmp_path / 'native-target', str(target))
    manifest = dict(release=RELEASE, files={})
    for name in n.REQUIRED | {'app/execution/credential_broker_client.py'}:
        save(target / name, 'new code')
        manifest['files']['backend/' + name] = hashlib.sha256(b'new code').hexdigest()
    save(tmp_path / 'src/release.json', manifest)
    n.code_hashes(tmp_path)
    save(target / 'app/execution/cleanup_paths.py', 'old code')
    with pytest.raises(AssertionError, match='hash mismatch'):
        n.code_hashes(tmp_path)
    del manifest['files']['backend/app/execution/cleanup_paths.py']
    save(tmp_path / 'src/release.json', manifest)
    with pytest.raises(AssertionError, match='Shared cleanup'):
        n.code_hashes(tmp_path)


def test_prepare_uses_current_cli_runtime_and_runs_isolated_smoke_as_codex(tmp_path, monkeypatch):
    baseline, calls = rows(), []
    monkeypatch.setattr(n.m, 'private', save)
    monkeypatch.setattr(n.m, 'prepare_domestic_native', lambda source, release, previous:
                        calls.append(('prepare', str(previous))) or PurePosixPath(TARGET))
    monkeypatch.setattr(n, 'code_hashes', lambda *_: calls.append(('hashes',)))
    monkeypatch.setattr(n.m, 'run', lambda *a, **kw: calls.append(('run', a, kw)) or 'NATIVE_CLEANUP_SMOKE_PASS')
    n.prepare(tmp_path, tmp_path / 'src', RELEASE, baseline)
    assert calls[0] == ('prepare', str(Path(baseline[n.UNIT]['cwd'])))
    assert calls[1] == ('hashes',)
    assert calls[2][1][:4] == ('runuser', '-u', 'codex', '--')
    assert 'TemporaryDirectory' in calls[2][1][-1] and 'os.getuid() == 1001' in calls[2][1][-1]
    assert 'private-value' not in calls[2][1][-1]
    assert (tmp_path / 'NATIVE_PREPARED').exists()
