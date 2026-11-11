from contextlib import contextmanager
import os
from types import SimpleNamespace
import time

import pytest

from app.account_management import device


@pytest.mark.parametrize('with_proxy', [False, True])
def test_device_process_preserves_only_transport_and_parses_code(tmp_path, monkeypatch, with_proxy):
    keys = ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY',
            'http_proxy', 'https_proxy', 'all_proxy', 'no_proxy')
    proxy = {k: ('localhost,127.0.0.1' if 'no_proxy' == k.lower()
                 else 'http://127.0.0.1:7890') for k in keys} if with_proxy else {}
    host = {**proxy, 'OPENAI_API_KEY': 'never-inherit', 'SECRET': 'never-inherit',
            'CODEX_HOME': '/host/private', 'HOME': '/host/private'}
    monkeypatch.setattr(device, 'os', SimpleNamespace(environ=host, chmod=os.chmod))

    @contextmanager
    def directory(path, create=False):
        path.mkdir(exist_ok=True)
        yield SimpleNamespace(write=lambda name, content: (path / name).write_bytes(content))

    monkeypatch.setattr(device, 'directory', directory)
    seen, stopped = [], []
    process = SimpleNamespace(poll=lambda: None, returncode=None)

    def launch(argv, **kwargs):
        env = kwargs['env']
        assert argv == ['codex', 'login', '--device-auth']
        assert set(env) == {'HOME', 'CODEX_HOME', 'PATH', 'LANG', 'NO_COLOR', 'TERM'} | set(proxy)
        assert all(env[k] == v for k, v in proxy.items())
        assert env['HOME'] == str(tmp_path)
        assert env['CODEX_HOME'] == str(tmp_path / '.codex')
        kwargs['stdout'].write((device.VERIFICATION_URL + '\n\x1b[32mABCDE-1234\x1b[0m\n').encode())
        kwargs['stdout'].flush()
        return process

    monkeypatch.setattr(device.subprocess, 'Popen', launch)
    monkeypatch.setattr(device, 'stop_process', lambda p: stopped.append(p))
    monkeypatch.setattr(device.time, 'sleep', lambda _: None)
    assert not device.device_login(tmp_path, 'codex', lambda: bool(seen), seen.append, time.time() + 30)
    assert seen == ['ABCDE-1234']
    assert stopped == [process]
