"""Full database backup and restore tests for the joint domestic release."""
import copy
import pytest
from test_record_filters_release import module, save, RELEASE

v = module("domestic-record-filters-verify")


def test_full_rows_include_schema_and_retention_columns(monkeypatch):
    queries = []
    def query(db, statement):
        queries.append(statement)
        if 'FROM pg_tables' in statement:
            return 'alembic_version\ncli_retention\napi_worker_heartbeats'
        if statement == v.SCHEMA:
            return '{"columns":[],"constraints":[],"indexes":[]}'
        return '1:all-columns'
    monkeypatch.setattr(v.b, 'query', query)
    monkeypatch.setattr(v.s.p, 'columns', lambda _: {'alembic_version': ['version_num']})
    result = v.state(('db', 'user', 'name'))
    assert set(result['rows']) == {'alembic_version', 'cli_retention', 'api_worker_heartbeats'}
    assert result['columns'] == {'alembic_version': ['version_num']}
    assert all("-'" not in q for q in queries)


@pytest.fixture
def backup_env(tmp_path, monkeypatch):
    work = tmp_path / 'work'
    work.mkdir()
    for name in ('EXECUTORS_STOPPED', 'CLEANUP_STOPPED', 'edge-before.conf', 'web-before.conf', 'domestic-compose.private.json'):
        save(work / name, 'fixture')
    before = {'rows': {'alembic_version': '1:0032', 'receipts': '2:unchanged'},
              'columns': {'receipts': ['id', 'deleted_at']}, 'schema': {'columns': ['same']}}
    monkeypatch.setattr(v.m, 'APP', tmp_path / 'absent')
    monkeypatch.setattr(v.m, 'private', save)
    monkeypatch.setattr(v.s.n, 'backup', lambda *_: None)
    monkeypatch.setattr(v.b, 'dump', lambda db, path: path.write_bytes(b'dump'))
    monkeypatch.setattr(v.b, 'secure_tree', lambda *_: None)
    monkeypatch.setattr(v, 'state', lambda _: copy.deepcopy(before))
    return work, tmp_path / 'backup', {'domestic': {'files': {}}, 'nativeFiles': {}}, before


def test_backup_restore_compares_rows_schema_columns(backup_env, monkeypatch):
    work, destination, data, before = backup_env
    original = v.b.fingerprint
    def restored(db, path, expected, release, group):
        assert expected == before
        assert v.b.fingerprint(('isolated', 'postgres', 'postgres')) == before
    monkeypatch.setattr(v.b, 'restore_check', restored)
    v.backup(work, destination, data, RELEASE)
    assert v.b.fingerprint is original
    assert (destination / 'COMPLETE').exists()
    v.preserved(destination)
    monkeypatch.setattr(v, 'state', lambda _: {**before, 'columns': {}})
    with pytest.raises(AssertionError, match='Database changed'):
        v.preserved(destination)


def test_restore_failure_never_marks_complete_and_resets_helper(backup_env, monkeypatch):
    work, destination, data, _ = backup_env
    original = v.b.fingerprint
    def fail(*_):
        raise AssertionError('restored mismatch')
    monkeypatch.setattr(v.b, 'restore_check', fail)
    with pytest.raises(AssertionError, match='restored mismatch'):
        v.backup(work, destination, data, RELEASE)
    assert v.b.fingerprint is original
    assert not (destination / 'COMPLETE').exists()


