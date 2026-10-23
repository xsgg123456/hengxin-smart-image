"""No live production commands: baseline, phase and worker-only deployment invariants."""
import importlib.util
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import studio_delivery_runtime as r

spec = importlib.util.spec_from_file_location('studio_delivery_deploy',
                                             Path(__file__).with_name('studio-delivery-deploy.py'))
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value if isinstance(value, str) else json.dumps(value))


def argv(root):
    return [str(root / '.venv/bin/python'), str(root / '.venv/bin/celery'), '-A',
            'app.overseas.execution.worker:celery_app', 'worker', '--pool=prefork',
            '--concurrency=5', '--loglevel=INFO', '--hostname=overseas@racknerd-058889d',
            '--queues=overseas.cli']


def manifest(work, name='app/overseas/studio/delivery.py', baseline=None):
    path = work / 'src/backend' / name
    save(path, 'new source')
    files = {name: dict(baseline=baseline, sha256=r.digest(path))}
    save(work / 'patch.json', dict(files=files))
    return files


@pytest.mark.parametrize('name', ['../delivery.py', '/tmp/injected.py',
                                 'app/overseas/auth/router.py', 'app/overseas/studio/../config.py'])
def test_manifest_rejects_outside_allowlist(tmp_path, name):
    save(tmp_path / 'patch.json', {'files': {name: {'baseline': None, 'sha256': '0' * 64}}})
    with pytest.raises(RuntimeError, match='allowlist'):
        r.patch(tmp_path)


@pytest.mark.parametrize('value', ['bad', 'A' * 64, 5, None])
def test_rejects_invalid_hash(tmp_path, value):
    files = manifest(tmp_path)
    files[next(iter(files))]['sha256'] = value
    save(tmp_path / 'patch.json', dict(files=files))
    with pytest.raises(RuntimeError, match='Invalid hash'):
        r.patch(tmp_path)


def test_patch_and_live_baseline_bound_to_actual_bytes(tmp_path):
    files = manifest(tmp_path)
    assert r.patch(tmp_path) == files
    r.baseline(tmp_path, files)
    name = next(iter(files))
    save(tmp_path / name, 'unexpected existing baseline')
    with pytest.raises(RuntimeError, match='baseline'):
        r.baseline(tmp_path, files)
    save(tmp_path / 'src/backend' / name, 'changed')
    with pytest.raises(RuntimeError, match='checksum'):
        r.patch(tmp_path)


def test_rejects_linked_parent(tmp_path):
    actual, link = tmp_path / 'actual', tmp_path / 'link'
    actual.mkdir()
    try:
        link.symlink_to(actual, target_is_directory=True)
    except OSError:
        pytest.skip('Host cannot create directory symlinks')
    with pytest.raises(RuntimeError, match='Symlink'):
        r.safe(link / 'not-yet-created')


def test_tree_binds_non_python_files_and_excludes_only_runtime_caches(tmp_path):
    save(tmp_path / 'app/data.json', 'config')
    save(tmp_path / 'app/code.py', 'code')
    save(tmp_path / '.venv/bin/python', 'dependency')
    save(tmp_path / 'app/__pycache__/code.pyc', 'bytecode')
    assert set(r.tree(tmp_path)) == {'app/data.json', 'app/code.py'}


def test_dropin_preserves_all_actual_parameters_and_only_changes_paths(monkeypatch):
    # Posix paths make exact systemd rendering portable on the Windows test host.
    from pathlib import PurePosixPath
    root = PurePosixPath('/opt/old/backend')
    monkeypatch.setattr(r, 'Path', PurePosixPath)
    monkeypatch.setattr(r, 'TARGET', PurePosixPath('/opt/new/backend'))
    saved = dict(old=str(root), argv=argv(root))
    text = r.dropin(saved)
    assert text.splitlines()[:3] == ['[Service]', 'WorkingDirectory=/opt/new/backend', 'ExecStart=']
    assert text.splitlines()[3] == 'ExecStart=' + ' '.join(argv(r.TARGET))
    assert all(word not in text for word in ('Environment=', 'User=', 'Group=', 'outbox', 'domestic'))


def test_unexpected_worker_arguments_rejected(tmp_path):
    command = argv(tmp_path)
    command[-1] = '--queues=celery'
    with pytest.raises(RuntimeError, match='Unexpected actual'):
        r.arguments(tmp_path, command)


@pytest.mark.parametrize('marker', [None, 'stale'])
def test_install_test_receipt_required_before_service_calls(tmp_path, monkeypatch, marker):
    save(tmp_path / 'phase.json', dict(phase='prepared'))
    save(tmp_path / 'patch.json', '{}')
    save(tmp_path / 'prepared.json', dict(manifest=r.digest(tmp_path / 'patch.json')))
    if marker:
        save(tmp_path / 'INSTALL_TESTS_PASSED', marker)
    calls = []
    monkeypatch.setattr(r, 'run', lambda *a, **kw: calls.append(a))
    with pytest.raises((FileNotFoundError, RuntimeError)):
        d.switch(tmp_path)
    assert not calls


@pytest.mark.parametrize('phase', ['draining', 'stopped', 'started', 'verified', 'resume-requested'])
def test_switch_attempt_cannot_be_repeated(tmp_path, monkeypatch, phase):
    save(tmp_path / 'phase.json', dict(phase=phase))
    monkeypatch.setattr(d, 'validate', lambda _: pytest.fail('Must reject before validation'))
    with pytest.raises(RuntimeError, match='prior switch'):
        d.switch(tmp_path)


def setup_switch(work, monkeypatch):
    old = work / 'old'
    saved = dict(old=str(old), pid=123, argv=argv(old))
    state = dict(worker=saved)
    save(work / 'phase.json', dict(phase='prepared'))
    save(work / 'unit-before.txt', 'unit')
    monkeypatch.setattr(d, 'validate', lambda _: state)
    monkeypatch.setattr(r, 'live', lambda: saved.copy())
    monkeypatch.setattr(r, 'unit', lambda: 'unit')
    monkeypatch.setattr(r, 'DROP', work / 'unit.d/zzzz-release.conf')
    return saved


def test_failed_drain_never_stops_worker_or_writes_override(tmp_path, monkeypatch):
    setup_switch(tmp_path, monkeypatch)
    calls = []
    monkeypatch.setattr(r, 'run', lambda *a, **kw: calls.append(a))
    monkeypatch.setattr(r, 'gate', lambda *a, **kw: dict(before=False, paused=bool(a), active=1))
    ticks = iter([0, 2])
    monkeypatch.setattr(d.time, 'monotonic', lambda: next(ticks))
    with pytest.raises(RuntimeError, match='deadline'):
        d.switch(tmp_path, drain_seconds=1)
    assert not calls and not r.DROP.exists()
    assert r.read(tmp_path / 'phase.json')['phase'] == 'draining'


def test_idle_drain_stops_only_overseas_worker_and_requires_backup_before_override(tmp_path, monkeypatch):
    setup_switch(tmp_path, monkeypatch)
    calls = []
    monkeypatch.setattr(r, 'gate', lambda *a, **kw: dict(before=True, paused=True, active=0))
    monkeypatch.setattr(r, 'run', lambda *a, **kw: calls.append(a) or ('0' if 'show' in a else ''))
    monkeypatch.setattr(r, 'backup', lambda _: (_ for _ in ()).throw(RuntimeError('backup failed')))
    with pytest.raises(RuntimeError, match='backup failed'):
        d.switch(tmp_path)
    assert calls == [('systemctl', 'stop', r.UNIT), ('systemctl', 'show', r.UNIT, '-p', 'MainPID', '--value')]
    assert not r.DROP.exists()
    assert r.read(tmp_path / 'phase.json')['phase'] == 'stopped'


def test_gate_uses_short_transaction_and_never_blocks_enqueue_by_mutating_jobs(monkeypatch):
    calls = []
    monkeypatch.setattr(r, 'run', lambda *a, **kw: calls.append((a, kw)) or '{}')
    r.gate('pause')
    args, options = calls[0]
    assert args[:4] == ('docker', 'exec', '-i', r.API)
    code = options['input']
    assert 'with session_factory().begin()' in code and 'lock_gate(s)' in code
    assert 'Job.status.in_(ACTIVE)' in code and 'g.paused = True' in code
    assert 'job.status =' not in code and 'sleep' not in code


@pytest.mark.parametrize('original', [True, False])
def test_resume_restores_exact_previous_pause_value(tmp_path, monkeypatch, original):
    save(tmp_path / 'phase.json', dict(phase='verified'))
    save(tmp_path / 'gate-before.json', dict(paused=original))
    save(tmp_path / 'ACCEPTANCE_PASSED', 'manifest-sha')
    monkeypatch.setattr(d, 'verify', lambda _: dict(manifest='manifest-sha'))
    calls = []
    monkeypatch.setattr(r, 'gate', lambda *a, **kw: calls.append((a, kw)) or dict(paused=original))
    d.resume(tmp_path)
    assert calls == [(('resume',), dict(paused=original))]
    assert r.read(tmp_path / 'phase.json')['phase'] == 'resumed'


def test_resume_requires_recovery_acceptance_receipt(tmp_path, monkeypatch):
    save(tmp_path / 'phase.json', dict(phase='verified'))
    monkeypatch.setattr(d, 'verify', lambda _: dict(manifest='sha'))
    monkeypatch.setattr(r, 'gate', lambda *a, **kw: pytest.fail('Must remain paused'))
    with pytest.raises(FileNotFoundError):
        d.resume(tmp_path)


@pytest.mark.parametrize('phase', ['prepared', 'stopped', 'started', 'resumed'])
def test_resume_requires_verified_phase(tmp_path, monkeypatch, phase):
    save(tmp_path / 'phase.json', dict(phase=phase))
    monkeypatch.setattr(d, 'verify', lambda _: pytest.fail('Must reject before verification'))
    with pytest.raises(RuntimeError, match='verified'):
        d.resume(tmp_path)


@pytest.mark.parametrize('changed', ['manifest', 'patch', 'original', 'installed'])
def test_validation_rejects_bound_content_drift(tmp_path, monkeypatch, changed):
    save(tmp_path / 'patch.json', '{}')
    fingerprint = r.digest(tmp_path / 'patch.json')
    save(tmp_path / 'INSTALL_TESTS_PASSED', fingerprint)
    state = dict(manifest='wrong' if changed == 'manifest' else fingerprint,
                 files={'file': 'hash'}, worker={'old': str(tmp_path / 'old')},
                 source={'source': 'hash'}, installed={'installed': 'hash'})
    save(tmp_path / 'prepared.json', state)
    monkeypatch.setattr(r, 'patch', lambda _: {} if changed == 'patch' else state['files'])
    def tree(path):
        key = 'source' if path == tmp_path / 'old' else 'installed'
        return {} if changed == ('original' if key == 'source' else key) else state[key]
    monkeypatch.setattr(r, 'tree', tree)
    with pytest.raises(RuntimeError, match='drift'):
        d.validate(tmp_path)


def test_stopping_failure_never_writes_override_or_restarts(tmp_path, monkeypatch):
    setup_switch(tmp_path, monkeypatch)
    monkeypatch.setattr(r, 'gate', lambda *a, **kw: dict(before=True, paused=True, active=0))
    calls = []
    def fail(*args, **kwargs):
        calls.append(args)
        raise RuntimeError('stop outcome unknown')
    monkeypatch.setattr(r, 'run', fail)
    with pytest.raises(RuntimeError, match='unknown'):
        d.switch(tmp_path)
    assert calls == [('systemctl', 'stop', r.UNIT)]
    assert not r.DROP.exists()
    assert r.read(tmp_path / 'phase.json')['phase'] == 'stop-requested'


def test_vendor_or_runtime_later_override_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(r, 'DROP', tmp_path / 'zzzz-release.conf')
    for location in ('/run/systemd/system', '/usr/lib/systemd/system'):
        with pytest.raises(RuntimeError, match='Later override'):
            r.last_override('# ' + location + '/' + r.UNIT + '.d/zzzzzz-later.conf\n[Service]')
    r.last_override('# /etc/systemd/system/' + r.UNIT + '.d/10-original.conf\n[Service]')


def test_release_sorts_after_existing_production_overrides(tmp_path, monkeypatch):
    actual_name = r.DROP.name
    monkeypatch.setattr(r, 'DROP', tmp_path / actual_name)
    names = ['50-resources.conf', '90-overseas-update.conf', '95-codex-astra.conf',
             '99-overseas-upload.conf', 'zzzz-codex-auth-20261019.conf',
             'zzzzz-archive-deletion-20261019.conf', 'zzzzzz-studio-reopen-20261019.conf',
             'zzzzzzz-skill-availability-20261022.conf', 'zzzzzzzz-any-file-20261022.conf']
    for name in names:
        (tmp_path / name).write_text('[Service]\n')
    r.last_override('\n'.join('# /etc/systemd/system/' + r.UNIT + '.d/' + name
                              for name in names))
    with pytest.raises(RuntimeError, match='Later override'):
        r.last_override('# /run/systemd/system/' + r.UNIT + '.d/zzzzzzzzzz-newer.conf')


def test_installed_unit_receipt_uses_reloaded_dropin_list(tmp_path, monkeypatch):
    setup_switch(tmp_path, monkeypatch)
    monkeypatch.setattr(r, 'dropin', lambda _: '[Service]\nWorkingDirectory=/opt/new/backend\n')
    state = {'reloaded': False}
    calls = []
    monkeypatch.setattr(r, 'unit', lambda: 'unit\nnew-dropin' if state['reloaded'] else 'unit')
    monkeypatch.setattr(r, 'gate', lambda *a, **kw: dict(before=True, paused=True, active=0))
    monkeypatch.setattr(r, 'backup', lambda _: None)
    def run(*args, **kwargs):
        calls.append(args)
        if args == ('systemctl', 'daemon-reload'):
            state['reloaded'] = True
        if args == ('systemctl', 'start', r.UNIT):
            assert (tmp_path / 'unit-installed.txt').read_text() == 'unit\nnew-dropin'
        return '0' if 'show' in args else ''
    monkeypatch.setattr(r, 'run', run)
    def verify(work):
        assert r.read(work / 'phase.json')['phase'] == 'started'
        assert (work / 'unit-installed.txt').read_text() == r.unit()
    monkeypatch.setattr(d, 'verify', verify)
    d.switch(tmp_path)
    assert calls.index(('systemctl', 'daemon-reload')) < calls.index(('systemctl', 'start', r.UNIT))
