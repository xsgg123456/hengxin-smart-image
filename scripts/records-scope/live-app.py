"""Isolated loopback QA: real API + production dist, SQLite and memory images.

Run with backend/.venv/Scripts/python.exe scripts/records-scope/live-app.py.
No production credentials, background workers, paid upstream, or persistent data.
"""
import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
from threading import Lock
from uuid import UUID
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / 'hengxin-smart-image/backend'
sys.path[:0] = [str(BACKEND), str(BACKEND / 'tests')]
os.environ.update(APP_ENV='test', HX_BUSINESS_CONTEXT='domestic',
    DATABASE_URL='postgresql+psycopg://qa:qa@127.0.0.1:1/records_scope_test',
    ENABLE_DEV_IDENTITY='false', ENABLE_CODEX_EXECUTOR='false',
    MINIO_ACCESS_KEY='isolated-test', MINIO_SECRET_KEY='isolated-test',
    API_IMAGE_ENABLED='true', API_IMAGE_API_KEY='',
    IDENTITY_SERVICE_URL='', IDENTITY_SERVICE_KEY='', IDENTITY_PUBLIC_ORIGIN='')

from fastapi import Cookie, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.models import Base
from app.db.session import get_session
from app.modules.auth.dependencies import get_identity_id
from app.resource_models import UserRecord
from app.storage.minio_store import get_store
from app.modules.api_image_edits.models import ApiFile, ApiItem, ApiTask
from files_helpers import MemoryStore, image_bytes

OUTPUT = ROOT / 'output/records-scope-formal'
OUTPUT.mkdir(parents=True, exist_ok=True)
engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
Base.metadata.create_all(engine)
factory = sessionmaker(engine, expire_on_commit=False)
database_lock = Lock()  # StaticPool has one SQLite connection: serialize its sessions.
store = MemoryStore()
people = [UUID(int=n) for n in range(101, 105)]
faults = {'tasks': False, 'creators': False}
beijing = ZoneInfo('Asia/Shanghai')
today = datetime.now(beijing).replace(hour=0, minute=0, second=0, microsecond=0)
manifest = {'today': today.date().isoformat(), 'users': [str(x) for x in people], 'tasks': []}


def seed():
    data = image_bytes()
    with factory.begin() as session:
        for index, name in enumerate(['隔离验收本人', '同名创建人', '同名创建人', '无记录验收账号']):
            session.add(UserRecord(id=people[index], name=name, role='operator',
                status='disabled' if index == 2 else 'active', identity_source='development'))
        file = ApiFile(id=UUID(int=501), owner_id=people[0], name='隔离样本.png',
            bucket='qa-memory', object_key='api-image-edits/qa/sample.png', content_type='image/png',
            checksum=hashlib.sha256(data).hexdigest(), size_bytes=len(data), width=8, height=6,
            status='ready')
        session.add(file)
        store.put(file, data)
        states = ['succeeded', 'partial_failed', 'failed', 'queued', 'running', 'uncertain']
        for index in range(52):
            owner = 0 if index < 25 else 1 if index < 41 else 2
            state = states[index % len(states)]
            created = today - timedelta(days=index % 40) + timedelta(hours=12)
            # Include both Beijing day boundaries and an explicitly deleted row.
            if index == 0:
                created = today
            if index == 1:
                created = today + timedelta(days=1, microseconds=-1)
            identifier = UUID(int=1001 + index)
            task = ApiTask(id=identifier, owner_id=people[owner], operator_id=people[(owner + 1) % 3],
                name=f'隔离验收任务 {index + 1:02d}', prompt='本地只读验收，无生成请求', material_id=file.id,
                parameters={}, state=state, events=[], created_at=created.astimezone(timezone.utc),
                updated_at=created.astimezone(timezone.utc),
                deleted_at=today.astimezone(timezone.utc) if index == 51 else None)
            session.add(task)
            item_states = ['succeeded', 'succeeded'] if state == 'succeeded' else ['succeeded', 'failed'] if state == 'partial_failed' else ['failed', 'failed'] if state == 'failed' else [state, state]
            for position, item_state in enumerate(item_states, 1):
                session.add(ApiItem(id=UUID(int=10001 + index * 2 + position), task_id=identifier,
                    position=position, source_id=file.id, result_id=file.id if item_state == 'succeeded' else None,
                    state=item_state))
            if index != 51:
                manifest['tasks'].append({'id': str(identifier), 'owner': str(people[owner]),
                    'state': state, 'day': created.date().isoformat(), 'name': task.name,
                    'success': item_states.count('succeeded'), 'failed': item_states.count('failed')})
    (OUTPUT / 'fixture.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')


def database():
    with database_lock, factory() as session:
        yield session


def identity(qa_identity: str | None = Cookie(default=None)):
    return people[3] if qa_identity == 'empty' else people[0]


app.dependency_overrides[get_session] = database
app.dependency_overrides[get_identity_id] = identity
app.dependency_overrides[get_store] = lambda: store


@app.middleware('http')
async def isolated_guard(request: Request, call_next):
    path = request.url.path
    if request.method not in {'GET', 'HEAD'} and not path.startswith('/__qa__/'):
        return JSONResponse({'detail': 'Isolated QA forbids business writes'}, status_code=405)
    if path == '/api/v1/api-image-edits/tasks' and faults['tasks'] or path == '/api/v1/api-image-edits/creators' and faults['creators']:
        return JSONResponse({'detail': 'Isolated QA injected failure'}, status_code=503)
    return await call_next(request)


@app.get('/__qa__/fixture')
def fixture():
    return manifest


@app.post('/__qa__/faults')
async def set_faults(request: Request):
    values = await request.json()
    for key in faults:
        faults[key] = values.get(key) is True
    return faults


if __name__ == '__main__':
    import uvicorn
    try:
        seed()
        app.mount('/', StaticFiles(directory=BACKEND.parent / 'frontend/dist', html=True))
        uvicorn.run(app, host='127.0.0.1', port=18926, log_level='warning')
    finally:
        app.dependency_overrides.clear()
        store.objects.clear()
        engine.dispose()
