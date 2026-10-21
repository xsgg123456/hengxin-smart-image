import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('retention_drain', Path(__file__).with_name('retention-management-drain.py'))
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)


@pytest.fixture
def host(monkeypatch, tmp_path):
    events = []
    data = {'nativeSnapshots': {unit: {'pid': 1} for unit in d.n.UNITS}}
    monkeypatch.setattr(d.r, 'sql', lambda query: 't' if query.startswith('SELECT paused') else '0')
    monkeypatch.setattr(d.n, 'snapshot', lambda unit: data['nativeSnapshots'][unit])
    monkeypatch.setattr(d.n, 'show', lambda *_: '0')
    monkeypatch.setattr(d.n, 'stop', lambda unit: events.append(('native-stop', unit)))
    monkeypatch.setattr(d.p, 'graceful_stop', lambda service: events.append(('container-stop', service)))
    monkeypatch.setattr(d, 'wait_cli', lambda work: events.append(('wait-cli',)))
    monkeypatch.setattr(d.handoff, 'wait_idle', lambda *_: events.append(('wait-api',)))
    monkeypatch.setattr(d.handoff, 'database', lambda *_: {})
    monkeypatch.setattr(d.handoff, 'safe', lambda _: True)
    monkeypatch.setattr(d.m, 'private', lambda path, value: events.append(('save', path.name)))
    return tmp_path, data, events


def test_cleanup_stops_first_and_cli_producer_drains_before_worker(host):
    work, data, events = host
    d.stop(work, work, data)
    assert events[:2] == [('native-stop', d.n.RETENTION), ('native-stop', d.n.DELETE)]
    assert events.index(('wait-cli',)) < events.index(('container-stop', 'outbox'))
    assert events.count(('wait-cli',)) == 2
    assert events.index(('wait-api',)) < events.index(('native-stop', d.n.UNIT))
    assert events[-1] == ('save', 'EXECUTORS_STOPPED')


@pytest.mark.parametrize('phase', ['wait_cli', 'api', 'post-stop'])
def test_busy_or_unknown_never_force_stops_executors(host, monkeypatch, phase):
    work, data, events = host
    def fail(*args):
        raise RuntimeError('busy')
    if phase == 'wait_cli': monkeypatch.setattr(d, 'wait_cli', fail)
    elif phase == 'api': monkeypatch.setattr(d.handoff, 'wait_idle', fail)
    else: monkeypatch.setattr(d.handoff, 'safe', lambda _: False)
    with pytest.raises((RuntimeError, AssertionError)):
        d.stop(work, work, data)
    assert ('save', 'EXECUTORS_STOPPED') not in events
    if phase != 'post-stop':
        assert ('native-stop', d.n.UNIT) not in events
        assert ('container-stop', 'api-image-worker') not in events


def test_cli_wait_uses_two_independent_empty_checks(monkeypatch, tmp_path):
    values = iter(['1', '0', '0'])
    evidence = dict(states=[{'w': []}] * 3, queues={'celery': 0}, unacked=0)
    probes = []
    monkeypatch.setattr(d, 'native_probe', lambda *_: evidence)
    monkeypatch.setattr(d.m, 'run', lambda *args, **kw: next(values))
    monkeypatch.setattr(d.m, 'private', lambda path, value: probes.append(value))
    monkeypatch.setattr(d.time, 'sleep', lambda _: None)
    d.wait_cli(tmp_path)
    assert [row['stable'] for row in probes] == [0, 1, 2]


def test_cli_wait_has_a_bounded_deadline(monkeypatch, tmp_path):
    clock = iter([0, 2])
    monkeypatch.setattr(d.time, 'monotonic', lambda: next(clock))
    monkeypatch.setattr(d, 'native_probe', lambda *_: pytest.fail('No probe past deadline'))
    with pytest.raises(AssertionError, match='busy or unknown'):
        d.wait_cli(tmp_path, timeout=1)


def test_current_domestic_schema_without_retired_files_table():
    import os
    from uuid import uuid4
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url
    url = os.environ.get('TEST_DATABASE_URL')
    if not url:
        pytest.skip('Requires isolated TEST_DATABASE_URL')
    assert make_url(url).database.endswith('_test')
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                schema = 'retention_drain_' + uuid4().hex
                connection.execute(text('CREATE SCHEMA ' + schema))
                connection.execute(text('SET LOCAL search_path TO ' + schema))
                connection.execute(text('CREATE TABLE job_records(status text)'))
                connection.execute(text('CREATE TABLE api_edit_turns(status text)'))
                connection.execute(text('CREATE TABLE api_image_files(id uuid,status text,deleted_at timestamptz)'))
                connection.execute(text('CREATE TABLE image_variants(domain text,file_id uuid,completed bool,token uuid,lease_until timestamptz)'))
                query = text('SELECT (' + d.CLI + ') + (' + d.VARIANTS + ')')
                count = lambda: connection.scalar(query)
                assert connection.scalar(text("SELECT to_regclass('files')")) is None
                assert count() == 0
                identifier = uuid4()
                connection.execute(text("INSERT INTO api_image_files VALUES (:id,'ready',NULL)"), {'id': identifier})
                assert count() == 1  # Ready original has not been registered by variants yet.
                connection.execute(text("INSERT INTO image_variants VALUES ('api-image-edits',:id,true,NULL,NULL)"), {'id': identifier})
                assert count() == 0
                connection.execute(text("UPDATE image_variants SET token=:id"), {'id': uuid4()})
                assert count() == 1
                connection.execute(text("UPDATE image_variants SET token=NULL,lease_until=now()"))
                assert count() == 1
                connection.execute(text("UPDATE image_variants SET lease_until=NULL,completed=false"))
                assert count() == 1
                connection.execute(text("INSERT INTO job_records VALUES ('running')"))
                connection.execute(text("INSERT INTO api_edit_turns VALUES (NULL)"))
                assert count() == 3  # Unknown and running work still blocks stop.
            finally:
                transaction.rollback()
    finally:
        engine.dispose()
