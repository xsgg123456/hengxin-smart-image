from io import BytesIO
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import get_session
from app.main import app
from app.models import Base
from app.modules.auth.dependencies import get_identity_id
from app.resource_models import UserRecord
from app.storage.minio_store import get_store


def image_bytes(kind='PNG'):
    buffer = BytesIO()
    Image.new('RGB', (8, 6), '#012345').save(buffer, format=kind)
    return buffer.getvalue()


class ObjectStream:
    def __init__(self, data):
        self.data, self.closed, self.released = data, False, False

    def stream(self, size):
        yield self.data[:5]
        yield self.data[5:]

    def close(self):
        self.closed = True

    def release_conn(self):
        self.released = True


class MemoryStore:
    def __init__(self):
        self.objects, self.streams = {}, []
        self.fail_put = self.fail_remove = self.fail_open = False

    def put(self, record, data):
        assert record.object_key not in self.objects
        self.objects[record.object_key] = data
        if self.fail_put:
            raise OSError('injected store failure')

    def remove(self, record):
        if self.fail_remove:
            raise OSError('injected cleanup failure')
        self.objects.pop(record.object_key, None)

    def open(self, record):
        if self.fail_open:
            raise OSError('injected read failure')
        stream = ObjectStream(self.objects[record.object_key])
        self.streams.append(stream)
        return stream


@pytest.fixture
def files_env():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory.begin() as session:
        user = UserRecord(id=uuid4(), name='测试操作者', role='operator', status='active',
                          identity_source='development')
        session.add(user)
    identity = [user.id]
    store = MemoryStore()

    def database():
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = database
    app.dependency_overrides[get_identity_id] = lambda: identity[0]
    app.dependency_overrides[get_store] = lambda: store
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client, factory, store, identity
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
