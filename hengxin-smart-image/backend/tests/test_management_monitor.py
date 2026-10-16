from datetime import timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4
import subprocess

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy import event, select
from app.execution.diagnostics import failure_for
from app.core.config import get_settings
from app.models import Job, utcnow
from app.worker.models import WorkerHeartbeat
from app.resource_models import UserRecord
from app.worker import health as worker_health
from files_helpers import files_env





@pytest.mark.parametrize('version', ['codex-cli 0.153.4', 'codex-cli 0.1.0', 'secret output', None])
def test_worker_samples_version_disk_and_readiness(files_env, monkeypatch, tmp_path, version):
    env = files_env
    auth = tmp_path / 'auth.json'
    auth.write_text('{}')
    settings = get_settings()
    monkeypatch.setattr(settings, 'codex_binary', 'codex-test')
    monkeypatch.setattr(settings, 'codex_version', '0.153.4')
    monkeypatch.setattr(settings, 'codex_bwrap_binary', str(auth))
    monkeypatch.setattr(settings, 'codex_auth_file', str(auth))
    monkeypatch.setattr(settings, 'codex_execution_root', str(tmp_path))
    monkeypatch.setattr(worker_health.os, 'access', lambda *args: True)
    def run(argv, **kwargs):
        assert argv == ['codex-test', '--version'] and kwargs['timeout'] == 2
        if version is None:
            raise subprocess.TimeoutExpired(argv, 2)
        return SimpleNamespace(returncode=0, stdout=version)
    monkeypatch.setattr(worker_health.subprocess, 'run', run)
    sampled = []
    def disk(path):
        sampled.append(path)
        return SimpleNamespace(free=987654)
    monkeypatch.setattr(worker_health.shutil, 'disk_usage', disk)
    worker_health.pulse(env[1], concurrency=2)
    assert sampled == [str(tmp_path)]
    with env[1]() as session:
        beat = session.get(WorkerHeartbeat, settings.worker_node_name)
        assert beat.dependencies['freeDiskBytes'] == 987654
        assert beat.dependencies['concurrency'] == 2
        assert beat.dependencies['capacity'] == 2
        assert beat.state == ('ready' if version == 'codex-cli 0.153.4' else 'unavailable')
        assert 'secret' not in str(beat.dependencies)

def test_worker_missing_disk_keeps_unknown(files_env, monkeypatch):
    env = files_env
    monkeypatch.setattr(worker_health.subprocess, 'run', lambda *a, **k:
                        SimpleNamespace(returncode=1, stdout=''))
    def unavailable(path):
        raise OSError('private-worker-path')
    monkeypatch.setattr(worker_health.shutil, 'disk_usage', unavailable)
    worker_health.pulse(env[1])
    with env[1]() as session:
        data = session.get(WorkerHeartbeat, get_settings().worker_node_name).dependencies
        assert data['freeDiskBytes'] is None and data['concurrency'] is None
        assert 'private-worker-path' not in str(data)


