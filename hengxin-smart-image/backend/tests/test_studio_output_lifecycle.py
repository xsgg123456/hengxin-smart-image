"""Non-picture originals obey the existing deletion and archive lifetimes."""
from uuid import UUID
import runpy

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, select

from app.overseas.studio import conversation_cleanup
from app.overseas.studio.models import OutputFile, Conversation
from app.overseas.tasks.cleanup import cleanup_once
from studio_delivery_helpers import DeliveryCase, studio, materials, overseas
from test_studio_open_outputs import append_files
from test_overseas_task_deletion import request, archived
from studio_sessions_helpers import mutate, channel
from test_overseas_database import BACKEND


@pytest.mark.parametrize('scope', ['conversation', 'task'])
def test_output_erased_with_owner_and_archived_picture_retained(studio, monkeypatch, tmp_path, scope):
    case = DeliveryCase(studio, monkeypatch, tmp_path, count=1)
    append_files(case, monkeypatch, {'design.zip': b'original archive file'})
    case.run()
    output = case.current()['outputs'][0]
    picture = case.current()['pictures'][0]
    archive = archived(studio, [picture])
    with case.factory() as session:
        row = session.get(OutputFile, UUID(output['id']))
        key = row.object_key
        cid = session.scalar(select(Conversation.id))
    if scope == 'conversation':
        other = channel(case.client, case.task, 'keep')
        current = next(c for c in case.view()['conversations'] if c['id'] == str(cid))
        response = mutate(case.client, case.task, str(cid), 'DELETE', {'version': current['version']})
        assert response.status_code == 200, response.text
        assert conversation_cleanup.cleanup_once(case.factory, case.store) == 1
        with case.factory() as session:
            assert session.get(Conversation, UUID(other)) is not None
    else:
        assert request(case.client, case.task).status_code == 200
        assert cleanup_once(case.factory, case.store) == 1
    assert key not in case.store.data
    with case.factory() as session:
        assert session.get(OutputFile, UUID(output['id'])) is None
    assert case.client.get(output['url']).status_code == 404
    saved = case.client.get('/api/overseas/v1/archives/' + archive['id']).json()
    assert saved['pictureCount'] == 1
    assert case.client.get(saved['pictures'][0]['url']).status_code == 200


def test_output_table_upgrade_retains_existing_rows_and_matches_model(studio, monkeypatch, tmp_path):
    case = DeliveryCase(studio, monkeypatch, tmp_path, count=0)
    append_files(case, monkeypatch, {'empty.txt': b''})
    case.run()
    row = case.current()['outputs'][0]
    upgrade = runpy.run_path(str(BACKEND / 'migrations/overseas/versions/0022_studio_output_files.py'))['upgrade']
    with case.factory.begin() as session:
        connection = session.connection()
        with Operations.context(MigrationContext.configure(connection)):
            upgrade()
            upgrade()
        columns = {c['name'] for c in inspect(connection).get_columns(OutputFile.__tablename__)}
        assert columns == set(OutputFile.__table__.columns.keys())
        assert session.get(OutputFile, UUID(row['id'])).size_bytes == 0
    assert case.client.get(row['url']).content == b''
