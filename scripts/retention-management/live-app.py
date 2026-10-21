"""Loopback UI QA over real HTTP/PostgreSQL; only the image executor/store are fake."""
import os
from pathlib import Path
import sys
import tempfile
from datetime import timedelta
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / 'hengxin-smart-image/backend'
sys.path[:0] = [str(BACKEND), str(BACKEND / 'tests')]
from sqlalchemy.engine import make_url
url = os.environ['TEST_DATABASE_URL']
assert make_url(url).host in {'localhost', '127.0.0.1'}
assert make_url(url).database.endswith('_test')
os.environ.update(APP_ENV='test', HX_BUSINESS_CONTEXT='domestic', DATABASE_URL=url,
    ENABLE_DEV_IDENTITY='false', MINIO_ACCESS_KEY='test-access-key', MINIO_SECRET_KEY='test-secret-key',
    API_IMAGE_ENABLED='true', API_IMAGE_SEND_INTERVAL_SECONDS='0.000001', CLI_RETENTION_ENABLED='true')
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from fastapi.staticfiles import StaticFiles
import pytest
from app.main import app
from app.models import Base, utcnow
from app.db.session import get_session
from app.modules.auth.dependencies import get_identity_id
from app.resource_models import UserRecord
from app.storage.minio_store import get_store
from app.execution.models import ExecutionGate
from app.retention import api
from app.retention.objects import retry_objects
from app.retention.state import entry
from app.retention.service import begin_scan, end_scan, beating
from app.modules.api_image_edits.conversation_models import Conversation
from app.modules.api_image_edits.models import ApiItem, ApiTask
from files_helpers import MemoryStore
from test_api_cli_conversation import cli_enabled
from test_api_retention import sample

schema = 'qa_retention_' + uuid4().hex
admin = create_engine(url)
with admin.begin() as connection:
    connection.execute(text('CREATE SCHEMA ' + schema))
engine = create_engine(url, connect_args={'options': '-csearch_path=' + schema})
Base.metadata.create_all(engine)
factory = sessionmaker(engine, expire_on_commit=False)
store = MemoryStore()
with factory.begin() as session:
    user = UserRecord(id=uuid4(), name='自动清理隔离验收', role='operator', status='active', identity_source='development')
    session.add_all([user, ExecutionGate(id=1)])

def database():
    with factory() as session:
        yield session

app.dependency_overrides[get_session] = database
app.dependency_overrides[get_identity_id] = lambda: user.id
app.dependency_overrides[get_store] = lambda: store

def seed(tmp):
    patch = pytest.MonkeyPatch()
    try:
        settings = cli_enabled.__wrapped__(patch, Path(tmp))
        root, now = Path(settings.codex_execution_root), utcnow()
        with TestClient(app) as client:
            env = client, factory, store, [user.id]
            for name, age, action in [('历史已完成', 96, 'complete'), ('缓存已完成', 30, 'cache'),
                    ('文件失败待重试', 96, 'retry'), ('执行中受保护', 96, 'protected'),
                    ('尚未到期', 2, 'waiting'), ('下一轮到期清理', 96, 'due')]:
                identifier, _, _, _, _ = sample(env, patch, settings)
                with factory.begin() as session:
                    row = entry(session, 'api_cli', identifier)
                    row.initialized_at = now - timedelta(days=5)
                    row.last_activity_at = now - timedelta(hours=age)
                    row.next_cleanup_at = row.last_activity_at + timedelta(hours=24)
                    conv = session.get(Conversation, identifier)
                    item = session.get(ApiItem, conv.item_id)
                    session.get(ApiTask, item.task_id).name = name
                    if action == 'protected':
                        item.state = 'running'
                if action not in {'waiting', 'due'}:
                    api.process(factory, store, root, identifier, now)
                    store.fail_remove = action == 'retry'
                    retry_objects(factory, store, now=now)
                    store.fail_remove = False
            with factory.begin() as session:
                session.get(UserRecord, user.id).role = 'super_admin'
        run = begin_scan(factory, now)
        end_scan(factory, run, 'completed', now)
    finally:
        patch.undo()

if __name__ == '__main__':
    import uvicorn
    try:
        with tempfile.TemporaryDirectory(prefix='hx-retention-qa-') as tmp:
            seed(tmp)
            app.mount('/', StaticFiles(directory=BACKEND.parent / 'frontend/dist', html=True))
            with beating(factory):
                uvicorn.run(app, host='127.0.0.1', port=18925, log_level='warning')
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text('DROP SCHEMA ' + schema + ' CASCADE'))
        admin.dispose()
