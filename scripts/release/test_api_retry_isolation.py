"""Opt-in real Docker/PG checks; only uniquely named disposable local resources."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time
from uuid import uuid4

import pytest

pytestmark = pytest.mark.skipif(os.environ.get('HX_API_RETRY_DOCKER_TEST') != '1', reason='opt-in local Docker')


def load(path):
    spec = importlib.util.spec_from_file_location(path.stem.replace('-', '_'), path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def run(*args, **kwargs):
    return subprocess.check_output(args, text=True, encoding='utf-8', **kwargs).strip()


def test_real_compose_duration_and_stop_without_escalation(tmp_path, monkeypatch):
    d = load(Path(__file__).with_name('api-retry-deploy.py'))
    path = tmp_path / 'compose.json'
    path.write_text(json.dumps({'services': {'api': {'image': 'python:3.12.10-slim-bookworm',
        'stop_grace_period': '660s', 'environment': d.SETTINGS}}}))
    config = json.loads(run('docker', 'compose', '-p', 'retry-config-test', '-f', str(path), 'config', '--format', 'json'))
    assert config['services']['api']['stop_grace_period'] == '11m0s'
    name = 'hx-retry-stop-' + uuid4().hex[:10]
    try:
        run('docker', 'run', '-d', '--network', 'none', '--name', name, '--restart=unless-stopped',
            'python:3.12.10-slim-bookworm', 'python', '-u', '-c',
            'import signal,time; signal.signal(signal.SIGTERM, lambda *_: None); print("ready",flush=True); time.sleep(120)')
        deadline = time.monotonic() + 15
        while 'ready' not in run('docker', 'logs', name):
            assert time.monotonic() < deadline
            time.sleep(0.2)
        monkeypatch.setattr(d.m, 'container', lambda *_: name)
        with pytest.raises(subprocess.TimeoutExpired):
            d.graceful_stop('api-image-worker', timeout=1)
        assert json.loads(run('docker', 'inspect', name))[0]['State']['Running']
    finally:
        run('docker', 'rm', '-f', '-v', name)


def test_real_postgres_migration_repeated_and_dump_restore(tmp_path, monkeypatch):
    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    d = load(Path(__file__).with_name('api-retry-deploy.py'))
    migration = load(Path(__file__).resolve().parents[2] / 'hengxin-smart-image/backend/migrations/versions/0031_api_retry_policy.py')
    name = 'hx-retry-pg-' + uuid4().hex[:10]
    engine = None
    try:
        run('docker', 'run', '-d', '--name', name, '-p', '127.0.0.1::5432',
            '-e', 'POSTGRES_HOST_AUTH_METHOD=trust', 'postgres:17')
        deadline = time.monotonic() + 30
        while True:
            try:
                run('docker', 'exec', name, 'pg_isready', '-U', 'postgres')
                break
            except subprocess.CalledProcessError:
                assert time.monotonic() < deadline
                time.sleep(0.3)
        port = json.loads(run('docker', 'inspect', name))[0]['NetworkSettings']['Ports']['5432/tcp'][0]['HostPort']
        engine = sa.create_engine(f'postgresql+psycopg://postgres@127.0.0.1:{port}/postgres')
        with engine.begin() as conn:
            conn.exec_driver_sql('CREATE TABLE api_image_tasks(id uuid PRIMARY KEY, state text)')
            conn.exec_driver_sql('CREATE TABLE api_image_items(id uuid PRIMARY KEY, state text)')
            conn.exec_driver_sql('CREATE TABLE api_image_attempts(id uuid PRIMARY KEY, item_id uuid, state text)')
            conn.exec_driver_sql('CREATE TABLE api_image_channel(id integer PRIMARY KEY, paused boolean)')
            conn.exec_driver_sql("INSERT INTO api_image_items VALUES ('00000000-0000-0000-0000-000000000001','failed')")
            conn.exec_driver_sql("INSERT INTO api_image_attempts VALUES ('00000000-0000-0000-0000-000000000002','00000000-0000-0000-0000-000000000001','uncertain')")
            conn.exec_driver_sql('INSERT INTO api_image_channel VALUES (1,false)')
        database = (name, 'postgres', 'postgres')
        projection = d.columns(database)
        before = d.fingerprints(database, projection)
        dump = tmp_path / 'snapshot.dump'
        d.b.dump(database, dump)
        monkeypatch.setattr(d.b, 'fingerprint', lambda db: d.fingerprints(db, projection))
        d.b.restore_check(database, dump, before, uuid4().hex[:10], 'domestic')
        for _ in range(2):
            with engine.begin() as conn:
                with Operations.context(MigrationContext.configure(conn)):
                    migration.upgrade()
            assert d.fingerprints(database, projection) == before
        with engine.connect() as conn:
            assert conn.exec_driver_sql("SELECT retry_policy_version,attempts,retry_cycle_id FROM api_image_items").one() == ('legacy-v1', 1, None)
        with pytest.raises(RuntimeError, match='cannot be discarded'):
            migration.downgrade()
        assert d.fingerprints(database, projection) == before
    finally:
        if engine is not None:
            engine.dispose()
        run('docker', 'rm', '-f', '-v', name)
