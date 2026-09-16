"""Local worker configuration never inherits the fixture executor or production mode."""
import importlib.util
from pathlib import Path

import pytest


def load_worker():
    path=Path(__file__).resolve().parents[2]/'infra/local_codex_worker.py'
    spec=importlib.util.spec_from_file_location('local_codex_worker',path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def files(tmp_path, environment='test'):
    base=tmp_path/'base.env'
    base.write_text(f'APP_ENV={environment}\nPOSTGRES_PASSWORD=sample-test-only\nENABLE_FIXTURE_EXECUTOR=true\nPOSTGRES_PORT=55431\nMINIO_PORT=59002\nGENERATION_CONCURRENCY=2\n')
    local=tmp_path/'local.env'
    local.write_text('LOCAL_CODEX_BINARY=/opt/cli/codex\nLOCAL_CODEX_AUTH_FILE=/home/test/auth/auth.json\nLOCAL_CODEX_BWRAP=/usr/bin/bwrap\nLOCAL_CODEX_EXECUTION_ROOT=/home/test/execution\nLOCAL_CODEX_SKILL_ROOT=/home/test/skills\nLOCAL_CODEX_NODE=dedicated-test-node\nLOCAL_CODEX_REDIS_PORT=16388\n')
    return base,local


def test_local_worker_switches_only_executor_and_loopback_connections(tmp_path):
    values=load_worker().configuration(*files(tmp_path))
    assert values['ENABLE_FIXTURE_EXECUTOR']=='false'
    assert values['ENABLE_CODEX_EXECUTOR']=='true'
    assert values['DATABASE_URL']=='postgresql+psycopg://hengxin:sample-test-only@127.0.0.1:55431/hengxin'
    assert values['REDIS_URL']=='redis://127.0.0.1:16388/0'
    assert values['MINIO_ENDPOINT']=='127.0.0.1:59002'
    assert values['GENERATION_CONCURRENCY']=='2'
    assert values['WORKER_NODE_NAME']=='dedicated-test-node'


@pytest.mark.parametrize('environment',['production','', 'prod'])
def test_local_worker_refuses_implicit_or_production_environment(tmp_path,environment):
    with pytest.raises(ValueError,match='non-production'):
        load_worker().configuration(*files(tmp_path,environment))


def test_password_is_literal_and_url_encoded(tmp_path, monkeypatch):
    base, local = files(tmp_path)
    monkeypatch.setenv('UNEXPECTED_SECRET', 'must-not-expand')
    base.write_text(base.read_text().replace('sample-test-only', 'a@:/%${UNEXPECTED_SECRET}'))
    values = load_worker().configuration(base, local)
    assert 'a%40%3A%2F%25%24%7BUNEXPECTED_SECRET%7D@127.0.0.1' in values['DATABASE_URL']


@pytest.mark.parametrize('line', ['', 'LOCAL_CODEX_PROXY_URL', 'LOCAL_CODEX_PROXY_URL='])
def test_missing_proxy_always_clears_inherited_value(tmp_path, monkeypatch, line):
    base, local = files(tmp_path)
    local.write_text(local.read_text() + '\n' + line + '\n')
    monkeypatch.setenv('HENGXIN_CODEX_PROXY_URL', 'http://127.0.0.1:9999')
    values = load_worker().configuration(base, local)
    assert values['HENGXIN_CODEX_PROXY_URL'] == ''
