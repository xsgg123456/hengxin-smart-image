"""No Docker, WSL, services or model calls: exercise the real switch state machine."""
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

MODULE = Path(__file__).resolve().parents[2] / 'infra/local_codex_control.py'
spec = importlib.util.spec_from_file_location('local_codex_control', MODULE)
control = importlib.util.module_from_spec(spec)
original_path = sys.path[:]
try:
    sys.path.insert(0, str(MODULE.parent))
    spec.loader.exec_module(control)
finally:
    sys.path[:] = original_path
keeper = control.keeper_control

@pytest.fixture
def config(tmp_path, monkeypatch):
    monkeypatch.setattr(control, 'INFRA', tmp_path)
    for name in ('compose.yaml', 'compose.local-codex.yaml'):
        (tmp_path / name).write_text(MODULE.with_name(name).read_text(encoding='utf-8'), encoding='utf-8')
    base = tmp_path / '.env'
    base.write_text('APP_ENV=test\nPOSTGRES_PASSWORD=secret\nMINIO_ACCESS_KEY=user\nMINIO_SECRET_KEY=secret\n')
    local = tmp_path / '.env.local-codex'
    sample = MODULE.with_name('.env.local-codex.example').read_text(encoding='utf-8')
    local.write_text(sample, encoding='utf-8')
    return base, local

@pytest.mark.parametrize('project', ['other', 'hx-local-production', '-x', 'hx-local-a;whoami', 'hx-local-'])
def test_project_scope(config, project):
    with pytest.raises(control.Refused):
        control.configuration(project, *config)

@pytest.mark.parametrize('line', ['APP_ENV=production', 'APP_ENV=', 'APP_ENV=${APP_ENV}'])
def test_nonproduction_must_be_explicit(config, line):
    config[0].write_text(config[0].read_text().replace('APP_ENV=test', line))
    with pytest.raises(control.Refused):
        control.configuration('hx-local-test', *config)

def test_local_cannot_override_docker_secrets(config):
    config[1].write_text(config[1].read_text() + '\nPOSTGRES_PASSWORD=bad\n')
    with pytest.raises(control.Refused):
        control.configuration('hx-local-test', *config)

def test_explicit_files_override_ambient_configuration(config, monkeypatch):
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('DOCKER_HOST', 'ssh://remote')
    monkeypatch.setenv('ENABLE_CODEX_EXECUTOR', 'true')
    c = control.Controller('hx-local-test', *config)
    assert c.env['APP_ENV'] == 'test'
    assert 'DOCKER_HOST' not in c.env
    assert 'ENABLE_CODEX_EXECUTOR' not in c.env

@pytest.mark.parametrize('table', ['job_records', 'execution_rounds'])
@pytest.mark.parametrize('status', ['queued', 'uncertain', 'running', 'collecting', 'cancelling', 'future-state', None])
def test_database_gate_rejects_every_nonterminal_in_either_table(table, status):
    with sqlite3.connect(':memory:') as db:
        for name in ('job_records', 'execution_rounds'):
            db.execute(f'CREATE TABLE {name} (status TEXT)')
            db.executemany(f'INSERT INTO {name} VALUES (?)', [(s,) for s in ('succeeded', 'failed', 'partial', 'cancelled')])
        assert db.execute(control.IDLE_SQL).fetchone()[0] == 0
        db.execute(f'INSERT INTO {table} VALUES (?)', (status,))
        assert db.execute(control.IDLE_SQL).fetchone()[0] == 1

class Switch(control.Controller):
    def __init__(self, busy_at=None, fail_at=None):
        self.events, self.checks = [], 0
        self.busy_at, self.fail_at = busy_at, fail_at
        self.docker = ['docker']
        self.base = {'ENABLE_FIXTURE_EXECUTOR': 'true'}
        self.local = {'LOCAL_CODEX_REDIS_PORT': '16388'}
        self.api_running = True

    def inspect(self):
        self.events.append('inspect')

    def published_port(self, *args):
        self.events.append(('ports', *args))

    def prepare_unit(self, install=False):
        self.events.append('install-unit' if install else 'unit-check')

    def preflight(self):
        self.events.append('preflight')
        if self.fail_at == 'preflight':
            raise control.Refused('preflight failed')

    def ids(self, service):
        return ['api-id'] if service == 'api' and self.api_running else []

    def idle(self):
        self.checks += 1
        self.events.append('idle')
        if self.checks == self.busy_at:
            raise control.Refused('busy')

    def keeper(self, stop=False):
        self.events.append('keeper-stop' if stop else 'keeper-start')

    def stop_containers(self, services):
        self.events.append(('stop', tuple(services)))
        if 'api' in services:
            self.api_running = False

    def run(self, argv, **kwargs):
        self.events.append(tuple(argv))
        if argv == ['docker', 'start', 'api-id']:
            self.api_running = True

    def wsl(self, *args, **kwargs):
        self.events.append(args)
        return 'loaded'

    def worker_ready(self):
        self.events.append('ready')
        if self.fail_at == 'ready':
            raise control.Refused('unready')

    def compose_up(self, real, *services):
        self.events.append(('up', real, services))
        if services == ('api',):
            self.api_running = True
        if self.fail_at in services:
            raise control.Refused('failed up')

@pytest.mark.parametrize('action', ['start', 'stop', 'fixture'])
def test_busy_switch_never_touches_consumers_or_api(action):
    c = Switch(busy_at=1)
    with pytest.raises(control.Refused):
        c.execute(action)
    assert c.api_running
    assert not any(isinstance(e, tuple) and e[0] in ('stop', 'up', 'systemctl') for e in c.events)

@pytest.mark.parametrize('action', ['start', 'stop', 'fixture'])
def test_racing_submission_restores_only_original_api(action):
    c = Switch(busy_at=2)
    with pytest.raises(control.Refused):
        c.execute(action)
    assert c.api_running
    assert ('docker', 'start', 'api-id') in c.events
    assert ('stop', ('outbox', 'worker')) not in c.events

@pytest.mark.parametrize('failure', ['ready', 'outbox', 'api'])
def test_failure_after_switch_stays_closed(failure):
    c = Switch(fail_at=failure)
    with pytest.raises(control.Refused):
        c.execute('start')
    assert not c.api_running
    assert ('docker', 'start', 'api-id') not in c.events

def test_start_admits_only_after_worker_ready():
    c = Switch()
    c.execute('start')
    assert c.events.index('preflight') < c.events.index(('stop', ('api',)))
    assert c.events.index(('stop', ('outbox', 'worker'))) < c.events.index(('systemctl', 'restart', control.SERVICE))
    assert c.events.index(('ports', 'redis', '6379/tcp', '16388')) < c.events.index('ready')
    assert c.events.index('ready') < c.events.index(('up', True, ('api',)))

def test_fixture_stops_wsl_before_base_consumers_and_keeps_redis():
    c = Switch()
    c.execute('fixture')
    assert c.events.index(('systemctl', 'stop', control.SERVICE)) < c.events.index(('up', False, ('worker', 'outbox')))
    assert not any('redis' in str(e) for e in c.events)

def test_stop_leaves_admission_closed():
    c = Switch()
    c.execute('stop')
    assert not c.api_running
    assert not any(isinstance(e, tuple) and e[0] == 'up' for e in c.events)

def test_check_has_no_mutations():
    c = Switch()
    c.execute('check')
    assert c.events == ['inspect', 'unit-check', 'preflight', 'idle']

def test_unit_safely_quotes_spaces_percent_dollar_and_backslash():
    assert control.unit_quote('/a b/%i/$HOME/"x"\\') == '"/a b/%%i/$HOME/\\"x\\"\\\\"'
    with pytest.raises(control.Refused):
        control.unit_quote('/path\nUser=root')

def test_unit_creation_is_exclusive_and_refuses_foreign_unit(config, tmp_path):
    c = control.Controller('hx-local-test', *config)
    captured = []

    def wsl(*args, **kwargs):
        if args[0] == 'wslpath':
            return '/mnt/d/with spaces/' + Path(args[-1]).name
        if args[0] == '/usr/bin/python3':
            captured.append((args, kwargs))
        return ''

    c.wsl = wsl
    c.prepare_unit(install=True)
    args, kwargs = captured[0]
    unit, _ = json.loads(kwargs['input'])
    assert 'ExecStart=:' in unit and 'User=hengxin' in unit and 'KillMode=control-group' in unit
    assert 'secret' not in unit
    target = tmp_path / 'unit.service'
    command = [sys.executable, '-c', args[2], str(target), 'install']
    assert subprocess.run(command, input=kwargs['input'], text=True, capture_output=True).returncode == 0
    assert subprocess.run(command, input=kwargs['input'], text=True, capture_output=True).returncode == 0
    target.write_text('[Service]\nUser=root\n')
    assert subprocess.run(command, input=kwargs['input'], text=True, capture_output=True).returncode != 0
    assert target.read_text() == '[Service]\nUser=root\n'

def identity():
    return {'ProcessId': 123, 'ExecutablePath': str(Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'System32/wsl.exe'),
            'argv': ['wsl.exe', '-d', 'Ubuntu-24.04', '-u', 'hengxin', '--', 'sleep', 'infinity'],
            'CreationDate': 'original', 'CommandLine': 'wsl.exe -d Ubuntu-24.04 -u hengxin -- sleep infinity'}

def test_keeper_rejects_other_commands_and_users():
    value = identity()
    assert keeper.valid_keeper(value)
    value['argv'][-1] = '30'
    assert not keeper.valid_keeper(value)
    value = identity()
    value['argv'][4] = 'root'
    assert not keeper.valid_keeper(value)

@pytest.mark.parametrize('changed', [True, False])
def test_stop_never_kills_external_or_reused_keeper(config, tmp_path, monkeypatch, changed):
    path = tmp_path / 'keeper.json'
    monkeypatch.setattr(keeper, 'KEEPER_FILE', path)
    original = identity()
    path.write_text(json.dumps({'owner': None, 'identity': original}))
    current = original | {'CreationDate': 'reused'} if changed else original
    monkeypatch.setattr(keeper, 'keeper_identity', lambda *a: current)
    c = control.Controller('hx-local-test', *config)
    c.keeper(stop=True)  # Calling WinDLL/TerminateProcess here would fail the test on a fake PID.
    assert path.exists()

def test_subprocess_failure_does_not_leak_credentials(config, monkeypatch):
    c = control.Controller('hx-local-test', *config)
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: subprocess.CompletedProcess(a, 1, 'secret-url', 'secret-token'))
    with pytest.raises(control.Refused) as error:
        c.run(['fake'])
    assert 'secret' not in str(error.value)

@pytest.mark.parametrize('replacement', ['LOCAL_CODEX_USER=root', 'LOCAL_CODEX_REDIS_PORT=0',
                                         'LOCAL_CODEX_REDIS_PORT=65536', 'LOCAL_CODEX_PYTHON=relative'])
def test_invalid_runtime_config(config, replacement):
    key = replacement.split('=')[0]
    lines = config[1].read_text().splitlines()
    config[1].write_text('\n'.join(replacement if line.startswith(key + '=') else line for line in lines))
    with pytest.raises(control.Refused):
        control.configuration('hx-local-test', *config)

def test_preflight_failure_has_no_service_changes():
    c = Switch(fail_at='preflight')
    with pytest.raises(control.Refused):
        c.execute('start')
    assert c.api_running
    assert c.events == ['inspect', 'unit-check', 'preflight']

def test_foreign_container_refused_before_any_mutation(config):
    c = control.Controller('hx-local-test', *config)
    calls = []
    def run(argv, **kwargs):
        calls.append(argv)
        if 'context' in argv:
            return json.dumps([{'Endpoints': {'docker': {'Host': 'npipe:////./pipe/dockerDesktopLinuxEngine'}}}])
        if 'ps' in argv:
            return 'foreign-id'
        return json.dumps([{'Config': {'Labels': {'com.docker.compose.project': 'another-project'}}}])
    c.run = run
    with pytest.raises(control.Refused, match='does not belong'):
        c.inspect()
    assert all('stop' not in argv and 'up' not in argv for argv in calls)

def test_existing_external_keeper_is_adopted_without_ownership(config, tmp_path, monkeypatch):
    path = tmp_path / 'wsl-keeper.json'
    path.with_suffix('.pid').write_text('123')
    monkeypatch.setattr(keeper, 'KEEPER_FILE', path)
    monkeypatch.setattr(keeper, 'keeper_identity', lambda *a: identity())
    monkeypatch.setattr(subprocess, 'Popen', lambda *a, **k: pytest.fail('must reuse existing keeper'))
    c = control.Controller('hx-local-test', *config)
    c.keeper()
    assert json.loads(path.read_text()) == {'owner': None, 'identity': identity()}
    c.keeper(stop=True)
    assert path.exists()
