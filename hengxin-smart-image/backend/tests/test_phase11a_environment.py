"""No model calls; exercise process ownership, isolation and lifecycle failure paths."""
import importlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest


@pytest.fixture
def modules(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / 'infra'))
    return importlib.import_module('phase11a_environment'), importlib.import_module('phase11a_processes')


@pytest.fixture
def bare(modules):
    env = modules[0].Phase11AEnvironment.__new__(modules[0].Phase11AEnvironment)
    env.env, env.report = {'GENERATION_CONCURRENCY': '1'}, {}
    return env


def test_busy_database_blocks_change_before_stopping(bare):
    calls = []
    bare.command = lambda *a, **kw: '1'
    bare.stop_services = lambda: calls.append('stop')
    with pytest.raises(RuntimeError, match='not idle'):
        bare.set_concurrency(2)
    assert not calls and bare.env['GENERATION_CONCURRENCY'] == '1'


def test_race_after_stop_does_not_apply_new_concurrency(bare):
    calls = []
    results = iter(['0', '1'])
    bare.command = lambda *a, **kw: next(results)
    bare.stop_services = lambda: calls.append('stop')
    bare._start_services = lambda: calls.append('start')
    with pytest.raises(RuntimeError, match='not idle'):
        bare.set_concurrency(2)
    assert calls == ['stop'] and bare.env['GENERATION_CONCURRENCY'] == '1'


@pytest.mark.parametrize('value', [0, 3, True, '2', 2.0])
def test_invalid_concurrency_has_no_side_effect(bare, value):
    with pytest.raises(RuntimeError, match='Concurrency'):
        bare.set_concurrency(value)
    assert bare.env['GENERATION_CONCURRENCY'] == '1'


def test_idle_restart_and_concurrency_order(bare):
    calls = []
    bare._assert_idle = lambda: calls.append('idle')
    bare.stop_services = lambda: calls.append('stop')
    bare._start_services = lambda: calls.append('start-' + bare.env['GENERATION_CONCURRENCY'])
    bare.set_concurrency(2)
    bare.restart_services()
    assert calls == ['idle', 'stop', 'idle', 'start-2'] * 2
    assert bare.report == {'concurrency': 2, 'restarts': 1}


def test_docker_falls_back_when_wsl_wrapper_fails(bare, modules, monkeypatch):
    calls = []
    monkeypatch.setattr(modules[0].shutil, 'which', lambda name: '/tools/' + name)
    def run(args, **kwargs):
        calls.append(args[0])
        return SimpleNamespace(returncode=0 if args[0].endswith('.exe') else 1, stdout='29.5.3')
    monkeypatch.setattr(modules[0].subprocess, 'run', run)
    assert bare._docker() == '/tools/docker.exe'
    assert calls == ['/tools/docker', '/tools/docker.exe']


@pytest.mark.parametrize('kind', ['container', 'volume'])
def test_cleanup_refuses_foreign_resource_label(bare, kind):
    bare.tag, bare.docker = 'hx-p11a-own', 'docker'
    calls = []
    def command(args):
        calls.append(args)
        if 'ls' in args:
            return bare.tag + '-postgres'
        return json.dumps({'Labels': {'hengxin.phase11a': 'foreign'},
                           'Config': {'Labels': {'hengxin.phase11a': 'foreign'}}})
    bare.command = command
    with pytest.raises(RuntimeError, match='label mismatch'):
        bare.remove_resource(kind, bare.tag + '-postgres')
    assert all('rm' not in args for args in calls)
    with pytest.raises(RuntimeError, match='outside this run'):
        bare.remove_resource(kind, 'hx-local-test-postgres')


def test_container_has_private_ports_no_pull_and_both_labels(bare):
    bare.tag, bare.docker = 'hx-p11a-test', 'docker.exe'
    bare.containers, bare.volumes, bare.images = [], [], {'redis': 'redis@sha256:existing'}
    calls = []
    def command(args):
        calls.append(args)
        return '127.0.0.1:50123' if 'port' in args else 'created'
    bare.command = command
    assert bare.container('redis', 6379, '/data') == '127.0.0.1:50123'
    assert '--label' in calls[0] and '--label' in calls[1]
    assert '--pull=never' in calls[1] and '127.0.0.1::6379' in calls[1]
    assert bare.volumes == ['hx-p11a-test-redis-data']


def test_worker_injection_is_inside_private_process(bare):
    bare.tag, bare.worker_process = 'hx-p11a-test', None
    captured = []
    bare.start = lambda name, argv: captured.append((name, argv)) or 'process'
    bare.wait = lambda *args: True
    assert bare.start_worker(startup_code='sentinel = 42') == 'process'
    assert captured[0][0] == 'worker'
    assert captured[0][1][1].startswith('sentinel = 42\n')
    assert '--concurrency=1' in captured[0][1][1]


@pytest.mark.skipif(sys.platform != 'linux', reason='Linux pidfd ownership')
def test_wrong_birth_cannot_signal_existing_process(modules):
    p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'], start_new_session=True)
    try:
        modules[1].signal_owned(p.pid, 'wrong-birth', signal.SIGKILL)
        assert p.poll() is None
    finally:
        p.terminate()
        p.wait(timeout=5)


@pytest.mark.skipif(sys.platform != 'linux', reason='Linux independent process sessions')
def test_owned_children_stopped_foreign_process_untouched(bare, modules, tmp_path):
    bare.root, bare.python = tmp_path, Path(sys.executable)
    bare.env = {'PATH': '/usr/bin:/bin'}
    bare.init_processes()
    foreign = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'], start_new_session=True)
    try:
        code = ('import os,subprocess,sys,time\n'
                'p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(30)"],start_new_session=True)\n'
                f'open({str(tmp_path / "child")!r},"w").write(str(p.pid))\n'
                'time.sleep(30)')
        bare.worker_process = bare.start('worker', ['-c', code])
        deadline = time.monotonic() + 5
        while not (tmp_path / 'child').exists() and time.monotonic() < deadline:
            time.sleep(.05)
        child = int((tmp_path / 'child').read_text())
        bare.capture_descendants()
        assert child in bare.owned[bare.worker_process.pid]
        # Worker failure reparents its own-session child; birth tracking must survive it.
        root = next(pid for pid in bare.owned[bare.worker_process.pid]
                    if pid != bare.worker_process.pid and pid != child)
        modules[1].signal_owned(root, modules[1].process_stat(root)[2], signal.SIGKILL)
        bare.worker_process.wait(timeout=5)
        bare.stop_worker()
        info = modules[1].process_stat(child)
        assert not info or info[3] == 'Z'
        assert foreign.poll() is None
    finally:
        for p in bare.processes:
            bare._stop(p)
        bare._done.set()
        bare._watcher.join(timeout=2)
        foreign.terminate()
        foreign.wait(timeout=5)


@pytest.mark.skipif(sys.platform != 'linux', reason='WSL non-root startup cleanup')
def test_startup_failure_cleans_private_root_only(modules, tmp_path, monkeypatch):
    import pwd
    if os.getuid() == 0 or pwd.getpwuid(os.getuid()).pw_name != 'hengxin':
        pytest.skip('Requires the existing non-root WSL runtime')
    env = modules[0].Phase11AEnvironment(tmp_path / 'report')
    monkeypatch.setattr(env, '_boot', lambda: (_ for _ in ()).throw(RuntimeError('deliberate failure')))
    with pytest.raises(RuntimeError, match='deliberate failure'):
        with env:
            pass
    assert not env.root.exists() and (tmp_path / 'report').exists()
    assert env.report['cleanupComplete'] and env.report['defaultConcurrencyRestored']


def test_temporary_root_swap_is_not_deleted(bare, tmp_path):
    import threading
    bare.root = tmp_path / 'foreign'
    bare.root.mkdir()
    marker = bare.root / 'keep'
    marker.write_text('user data')
    bare.processes, bare.containers, bare.volumes = [], [], []
    bare._done = threading.Event()
    bare._watcher = SimpleNamespace(join=lambda **kwargs: None)
    with pytest.raises(RuntimeError, match='cleanup incomplete'):
        bare.cleanup()
    assert marker.read_text() == 'user data'
    assert not bare.report['cleanupComplete']


def test_failed_container_create_does_not_delete_anything(bare):
    bare.tag, bare.docker = 'hx-p11a-own', 'docker.exe'
    calls = []
    bare.command = lambda args: calls.append(args) or ''
    bare.remove_resource('container', 'hx-p11a-own-postgres')
    assert len(calls) == 1 and 'ls' in calls[0] and 'rm' not in calls[0]


@pytest.mark.skipif(sys.platform != 'linux', reason='Linux process timeout cleanup')
def test_command_timeout_and_error_never_export_credentials(bare, tmp_path):
    bare.root, bare.python = tmp_path, Path(sys.executable)
    bare.env = {'PATH': '/usr/bin:/bin'}
    bare.init_processes()
    try:
        with pytest.raises(RuntimeError, match='output suppressed') as error:
            bare.command(['-c', 'import sys; sys.stderr.write("secret-fixture-token"); sys.exit(2)'], app=True)
        assert 'secret-fixture-token' not in str(error.value)
        with pytest.raises(TimeoutError) as error:
            bare.command(['-c', 'import time; token="secret-fixture-token"; time.sleep(30)'], app=True, timeout=.1)
        assert 'secret-fixture-token' not in str(error.value)
        assert not bare.owned
    finally:
        bare._done.set()
        bare._watcher.join(timeout=2)
