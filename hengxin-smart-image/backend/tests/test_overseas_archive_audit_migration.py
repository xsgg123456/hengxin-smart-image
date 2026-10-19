"""Only unambiguous legacy confirmation evidence is eligible for backfill."""
import importlib.util
from pathlib import Path
from uuid import UUID
import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import select, delete
from app.overseas.archives.models import Archive, ArchiveAsset, ArchiveEvent
from app.overseas.tasks.models import TaskEvent
from test_overseas_task_deletion import deletion, generated, archived
from test_overseas_studio import studio
from test_overseas_materials import materials
from test_overseas_tasks import overseas


@pytest.mark.parametrize('evidence', ['complete', 'studio', 'missing', 'ambiguous', 'missing_asset'])
def test_migration_repeatable_and_never_guesses(deletion, evidence):
    _, factory, actor, task, _, _ = deletion
    rows = generated(deletion)
    archive = archived(deletion, rows)
    with factory.begin() as session:
        session.execute(delete(ArchiveEvent))
        record = session.get(Archive, UUID(archive['id']))
        if evidence != 'studio':
            record.versions = [v.removeprefix('studio:') for v in record.versions]
            for asset in session.scalars(select(ArchiveAsset)):
                asset.source_version = asset.source_version.removeprefix('studio:')
        if evidence != 'missing':
            for index in range(2 if evidence == 'ambiguous' else 1):
                session.add(TaskEvent(task_id=UUID(task['id']), kind='task.archived', actor_id=actor,
                    actor_name='有证据的归档人', title='整套归档', after_designer_id=UUID(task['designer']['id']), version=100 + index))
        if evidence == 'missing_asset':
            session.delete(session.scalar(select(ArchiveAsset)))
    path = Path(__file__).parents[1] / 'migrations/overseas/versions/0018_archive_events.py'
    spec = importlib.util.spec_from_file_location('archive_event_migration', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = factory.kw['bind']
    ArchiveEvent.__table__.drop(engine)
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            migration.upgrade()
    with factory() as session:
        events = session.scalars(select(ArchiveEvent)).all()
        if evidence == 'complete':
            assert len(events) == 1
            assert events[0].actor_name == '有证据的归档人' and events[0].actor_id == actor
            assert len(events[0].pictures) == 2 and not events[0].prior_history_unknown
            assert {p['id'] for p in events[0].pictures} == {str(p.id) for p in session.scalars(select(ArchiveAsset))}
        else:
            assert events == []
