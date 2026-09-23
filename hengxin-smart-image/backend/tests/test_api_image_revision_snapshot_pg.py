"""PostgreSQL JSON reference protection and reversible legacy migration."""
import importlib.util
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
from sqlalchemy import inspect, select, text

from app.modules.api_image_edits.files import delete_file, save_upload
from app.modules.api_image_edits.models import ApiItem, ApiTask
from app.modules.api_image_edits.schemas import ReviseItem
from app.modules.api_image_edits.service import submit
from app.modules.api_image_edits.versions import publish_result, revise
from app.modules.files.validation import validate_image
from files_helpers import image_bytes
from test_api_image_domain import enabled_api
from test_api_image_execution_pg import pg_api

pytestmark = pytest.mark.integration


def test_postgres_snapshot_only_json_reference_blocks_deletion(pg_api):
    factory, user, data, store = pg_api
    with factory() as session:
        image = validate_image(SimpleNamespace(file=BytesIO(image_bytes()), filename='material.png',
                                               content_type='image/png'))
        material = save_upload(session, store, user, image)
        data.materialFileId = material.id
        task_id = submit(session, user, data, 'create')
    with factory.begin() as session:
        task = session.get(ApiTask, task_id)
        item = session.scalar(select(ApiItem))
        publish_result(session, item, task, item.source_id)
        item.state = task.state = 'succeeded'
        item_id = item.id
    with factory() as session:
        revise(session, user, task_id, item_id, ReviseItem(baseVersion=1, text='修复'), 'revise')
    with factory.begin() as session:
        # Deliberately remove the ordinary FK reference so this probes JSONB/JSON
        # extraction itself, independent of source/material deletion guards.
        session.get(ApiTask, task_id).material_id = data.originalFileIds[0]
    with factory() as session:
        with pytest.raises(HTTPException) as error:
            delete_file(session, material.id, user)
        assert error.value.status_code == 409


def test_postgres_0017_roundtrip_and_refuses_frozen_snapshot_loss(pg_api):
    factory, user, data, _ = pg_api
    with factory() as session:
        submit(session, user, data, 'legacy')
    path = Path(__file__).parents[1] / 'migrations/versions/0017_api_revision_snapshot.py'
    spec = importlib.util.spec_from_file_location('migration_0017_pg', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with factory.kw['bind'].begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            module.downgrade()
            module.downgrade()
            assert 'revision_snapshot' not in {c['name'] for c in inspect(connection).get_columns('api_image_items')}
            module.upgrade()
            module.upgrade()
            assert connection.execute(text('SELECT revision_snapshot FROM api_image_items')).scalar() is None
            connection.execute(text("UPDATE api_image_items SET state='failed', revision_snapshot=:snapshot"),
                               {'snapshot': '{"fileIds": ["frozen"], "prompt": "p", "policyVersion": "v1"}'})
            with pytest.raises(RuntimeError, match='Cannot discard'):
                module.downgrade()
            connection.execute(text("UPDATE api_image_items SET revision_snapshot='null'"))
            module.downgrade()
            module.upgrade()
