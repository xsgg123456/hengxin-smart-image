import os
from types import SimpleNamespace

import pytest

from app.execution import workspace


@pytest.fixture
def command(tmp_path, monkeypatch):
    binary = tmp_path / 'codex'
    binary.touch()
    (tmp_path / 'codex-code-mode-host').touch()
    bwrap = tmp_path / 'bwrap'
    bwrap.touch()
    env = {'APP_ENV': 'test', 'HTTP_PROXY': 'http://untrusted.example:80', 'SECRET': 'private'}
    monkeypatch.setattr(workspace, 'os', SimpleNamespace(name='posix', environ=env))
    (tmp_path / 'home' / '.codex' / 'skills').mkdir(parents=True)
    ws = workspace.Workspace(tmp_path / 'home', tmp_path / 'work', tmp_path / 'control')
    return env, lambda: workspace.sandbox_command(ws, str(binary), ['--version'], str(bwrap))


def test_only_explicit_development_proxy_crosses_sandbox(command):
    env, build = command
    assert 'HTTP_PROXY' not in build()
    env['HENGXIN_CODEX_PROXY_URL'] = 'http://127.0.0.1:7890'
    argv = build()
    values = {argv[i+1]: argv[i+2] for i, v in enumerate(argv) if v == '--setenv'}
    assert values['HTTP_PROXY'] == values['https_proxy'] == 'http://127.0.0.1:7890'
    assert values['NO_PROXY'] == values['no_proxy'] == 'localhost,127.0.0.1,::1'
    assert 'private' not in argv and 'http://untrusted.example:80' not in argv
    assert '--clearenv' in argv


@pytest.mark.parametrize('proxy', ['http://remote:7890', 'http://user:pass@localhost:7890',
    'socks5://localhost:7890', 'http://localhost', 'http://localhost:0',
    'http://localhost:99999', 'http://localhost:7890/path', 'http://localhost:7890?q=x',
    'http://localhost:7890#x', 'http://local\nhost:7890'])
def test_invalid_proxy_refused(command, proxy):
    env, build = command
    env['HENGXIN_CODEX_PROXY_URL'] = proxy
    with pytest.raises(ValueError):
        build()


def test_local_proxy_refused_in_production(command):
    env, build = command
    env.update(APP_ENV='production', HENGXIN_CODEX_PROXY_URL='http://127.0.0.1:7890')
    with pytest.raises(ValueError):
        build()


@pytest.mark.parametrize('app_env', ['production', None])
def test_explicit_loopback_opt_in_for_service(command, app_env):
    env, build = command
    if app_env is None:
        env.pop('APP_ENV')
    else:
        env['APP_ENV'] = app_env
    env.update(HENGXIN_ALLOW_LOOPBACK_CODEX_PROXY='1',
               HENGXIN_CODEX_PROXY_URL='http://127.0.0.1:7890')
    argv = build()
    assert '--clearenv' in argv and 'private' not in argv
    values = {argv[i+1]: argv[i+2] for i, v in enumerate(argv) if v == '--setenv'}
    assert values['HTTPS_PROXY'] == 'http://127.0.0.1:7890'


@pytest.mark.parametrize('proxy', ['http://remote:7890', 'http://user:pass@localhost:7890',
    'http://localhost:7890/\x00', 'http://localhost:7890/\x7f'])
def test_opt_in_does_not_relax_proxy_validation(command, proxy):
    env, build = command
    env.update(APP_ENV='production', HENGXIN_ALLOW_LOOPBACK_CODEX_PROXY='1',
               HENGXIN_CODEX_PROXY_URL=proxy)
    with pytest.raises(ValueError):
        build()
