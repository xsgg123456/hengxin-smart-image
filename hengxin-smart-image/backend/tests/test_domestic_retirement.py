"""Real PostgreSQL migration chain and guarded domestic retirement."""
import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic import context
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, select, text, MetaData, Table
from sqlalchemy.orm import Session

from app.main import app
from app.models import Base, Job, Outbox, utcnow
from app.resource_models import UserRecord
from app.modules.api_image_edits.models import ApiFile
from app.modules.management.models import SystemSettings, SettingsAuditRecord
from app.capacity.models import CapacityReservation
from app.worker.models import WorkerHeartbeat
from app.modules.api_image_edits.deletion_models import ApiTaskDeletion
from app.retention.models import RetentionEntry, RetentionObject
from app.modules.files.variants import ImageVariants

ROOT = Path(__file__).resolve().parents[1]


def revision(number):
    path = next((ROOT / 'migrations/versions').glob(number + '_*.py'))
    spec = importlib.util.spec_from_file_location('revision_' + number, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def migrated_pg(monkeypatch):
    monkeypatch.setattr(context, 'is_offline_mode', lambda: False)
    url = os.getenv('TEST_DATABASE_URL')
    if not url:
        pytest.skip('Requires isolated TEST_DATABASE_URL')
    admin = create_engine(url)
    schema = 'retirement_' + uuid4().hex
    with admin.begin() as connection:
        connection.execute(text('CREATE SCHEMA ' + schema))
    engine = create_engine(url, connect_args={'options': '-csearch_path=' + schema})
    try:
        with engine.begin() as connection, Operations.context(MigrationContext.configure(connection)):
            for number in range(1, 30):
                revision(f'{number:04}').upgrade()
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text('DROP SCHEMA ' + schema + ' CASCADE'))
        admin.dispose()


def upgrade(engine):
    with engine.begin() as connection, Operations.context(MigrationContext.configure(connection)):
        revision('0030').upgrade()


def rows(connection, excluded=()):
    return {table: sorted(connection.execute(text('SELECT row_to_json(t)::text FROM "' + table +
            '" t')).scalars()) for table in inspect(connection).get_table_names() if table not in excluded}


def test_fresh_database_upgrades_and_runtime_metadata_excludes_retired_tables(migrated_pg):
    upgrade(migrated_pg)
    retired = set(revision('0030').RETIREMENT_CONTRACT['drop_tables'])
    assert not retired.intersection(inspect(migrated_pg).get_table_names())
    assert not retired.intersection(Base.metadata.tables)
    assert {'execution_gate', 'worker_heartbeats', 'api_task_deletions'}.issubset(inspect(migrated_pg).get_table_names())


def test_populated_api_and_shared_rows_preserved_exactly(migrated_pg, monkeypatch):
    with Session(migrated_pg) as session, session.begin():
        user = UserRecord(id=uuid4(), name='isolated', role='operator', status='active', identity_source='test')
        session.add(user)
        session.flush()
        file = ApiFile(id=uuid4(), owner_id=user.id, name='a.png', bucket='isolated', object_key='api-image-edits/' + uuid4().hex,
                       content_type='image/png', checksum='a' * 64, size_bytes=10, width=2, height=2, status='ready')
        session.add(file)
        session.flush()
        # This fixture deliberately remains at 0029. Seed its reflected shape,
        # not current ORM columns introduced by later migrations such as 0031.
        old = MetaData()
        tasks = Table('api_image_tasks', old, autoload_with=session.connection())
        items = Table('api_image_items', old, autoload_with=session.connection())
        task_id, now = uuid4(), utcnow()
        session.execute(tasks.insert().values(id=task_id, owner_id=user.id, operator_id=user.id,
            name='keep', prompt='keep', material_id=file.id, parameters={'frozen': True},
            state='succeeded', events=[], created_at=now, updated_at=now))
        session.execute(items.insert().values(id=uuid4(), task_id=task_id, source_id=file.id,
            result_id=file.id, position=1, state='succeeded', created_at=now, updated_at=now))
        for kind in ['api_cli_edit', 'skill_sync']:
            job = Job(id=uuid4(), idempotency_key=uuid4().hex, payload_hash='b' * 64, value='keep', kind=kind, status='succeeded')
            session.add(job)
            session.flush()
            session.add(Outbox(job_id=job.id, completed_at=utcnow()))
        session.add(RetentionEntry(domain='api_cli', resource_id=uuid4(), last_activity_at=utcnow(), initialized_at=utcnow()))
        session.add(ImageVariants(domain='api-image-edits', file_id=file.id, source_checksum=file.checksum))
        session.add(SystemSettings(id=1, version=3, values={'concurrency': 1, 'defaultSkillIds': {'text': 'old'}}))
        session.add(SettingsAuditRecord(operator_id=user.id, operator_name=user.name, version=3,
                    before={'defaultSkillIds': {'text': 'keep historical audit'}}, after={'concurrency':1}, fields=['defaultSkillIds']))
        session.add(CapacityReservation(id=uuid4(), kind='cli', owner_id=task_id, bytes=2048, state='held'))
        session.add(WorkerHeartbeat(node='keep', dependencies={'cli': True}))
        session.add(RetentionObject(bucket='isolated', object_key='pending-object', next_attempt_at=utcnow()))
        session.add(ApiTaskDeletion(task_id=uuid4(), actor_id=user.id, manifest={'files': []}))
    # Exercise the exact release projection SQL against the isolated PostgreSQL schema.
    path = ROOT.parents[1] / 'scripts/release/retirement-backup.py'
    spec = importlib.util.spec_from_file_location('retirement_release_backup', path)
    backup = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(backup)
    def query(database, statement):
        with migrated_pg.connect() as connection:
            schema = connection.scalar(text('SELECT current_schema()'))
            statement = statement.replace("schemaname='public'", "schemaname='" + schema + "'")
            statement = statement.replace('FROM public.', 'FROM "' + schema + '".')
            return '\n'.join(str(row[0]) for row in connection.execute(text(statement)))
    monkeypatch.setattr(backup.b, 'query', query)
    contract = backup.contract(ROOT.parent)
    projected = backup.fingerprint('isolated', contract)
    excluded = {*contract['drop_tables'], *contract['row_filters'], 'system_settings'}
    with migrated_pg.connect() as connection:
        before = rows(connection, excluded)
        api_job = connection.execute(text("SELECT row_to_json(t)::text FROM job_records t WHERE kind='api_cli_edit'")).scalar()
        api_outbox = connection.execute(text("SELECT row_to_json(t)::text FROM job_outbox t WHERE id IN (SELECT id FROM job_records WHERE kind='api_cli_edit')")).scalar()
        retained = {t: rows(connection)[t] for t in ('image_variants','cli_retention')}
    upgrade(migrated_pg)
    backup.compare(projected, backup.fingerprint('isolated'))
    with migrated_pg.connect() as connection:
        assert rows(connection, excluded) == before
        assert connection.execute(text('SELECT row_to_json(t)::text FROM job_records t')).scalar() == api_job
        assert connection.execute(text('SELECT row_to_json(t)::text FROM job_outbox t')).scalar() == api_outbox
        assert {t: rows(connection)[t] for t in retained} == retained
        assert connection.execute(text('SELECT "values" FROM system_settings')).scalar() == {'concurrency': 1}


@pytest.mark.parametrize('fault', ['nonempty', 'unknown_fk', 'active_job', 'variant', 'retention', 'job_reference'])
def test_refuses_unexpected_state_without_partial_deletion(migrated_pg, fault):
    with migrated_pg.begin() as connection:
        if fault == 'nonempty':
            connection.execute(text("INSERT INTO cleanup_objects VALUES (:id,'test','owned',now(),now())"), {'id': uuid4()})
        elif fault == 'unknown_fk':
            connection.execute(text('CREATE TABLE unexpected_reference (id uuid, file_id uuid REFERENCES files(id))'))
        elif fault == 'job_reference':
            with Session(bind=connection) as session:
                job = Job(id=uuid4(), idempotency_key=uuid4().hex, payload_hash='a'*64, value='old', kind='skill_sync', status='succeeded')
                session.add(job)
                session.flush()
                connection.execute(text('CREATE TABLE unknown_job_owner (job_id uuid REFERENCES job_records(id))'))
                connection.execute(text('INSERT INTO unknown_job_owner VALUES (:job)'), {'job': job.id})
        elif fault == 'active_job':
            with Session(bind=connection) as session:
                session.add(Job(idempotency_key=uuid4().hex, payload_hash='a'*64, value='old', kind='generation', status='running'))
                session.flush()
        elif fault == 'variant':
            with Session(bind=connection) as session:
                session.add(ImageVariants(domain='originals', file_id=uuid4(), source_checksum='a'*64, outputs={'256': {'checksum':'x'}}))
                session.flush()
        else:
            with Session(bind=connection) as session:
                session.add(RetentionEntry(domain='legacy_cli', resource_id=uuid4(), last_activity_at=utcnow(), status='active'))
                session.flush()
    with migrated_pg.connect() as connection:
        before = rows(connection)
    with pytest.raises(RuntimeError):
        upgrade(migrated_pg)
    with migrated_pg.connect() as connection:
        assert rows(connection) == before


def test_retired_http_routes_are_absent_and_shared_validator_still_imports():
    paths = app.openapi()['paths']
    for path in paths:
        assert not any(path.startswith('/api/v1/' + prefix) for prefix in
                       ['tasks', 'templates', 'archives', 'files', 'workspace', 'management/skills'])
    assert '/api/v1/api-image-edits/tasks' in paths
    from app.overseas.management.schemas import SkillRegisterInput
    from app.core.skill_package import validate_package
    assert validate_package
