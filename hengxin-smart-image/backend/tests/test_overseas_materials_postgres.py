"""Actual PostgreSQL contention between document binding, delete and retry."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID
from hashlib import sha256
from fastapi import HTTPException
import pytest
from app.overseas.auth.models import Member
from app.overseas.materials import files, service
from app.overseas.materials.models import Material, ParseVersion
from app.overseas.materials.schemas import SubmitMaterials
from test_overseas_members_postgres import pg_factory, member
from test_overseas_tasks_postgres import create
from test_overseas_materials import MemoryStore


def ready(factory, actor):
    store = MemoryStore()
    with factory.begin() as session:
        record = Material(owner_id=actor, kind='competitor', name='x.csv', bucket='test',
                          object_key='test-original', content_type='text/csv', size_bytes=3,
                          checksum=sha256(b'a,b').hexdigest(), status='ready', version=1)
        session.add(record)
        session.flush()
        session.add(ParseVersion(material_id=record.id, version=1, status='ready',
                                 parser_version='test', text='a,b'))
        store.put(record, b'a,b')
        return record.id, store


@pytest.mark.parametrize('other', ['delete', 'retry', 'bind'])
def test_binding_serializes_with_mutation(pg_factory, other):
    actor, designer = member(pg_factory, 'operator'), member(pg_factory, 'designer')
    first = create(pg_factory, actor, designer, 'one')[1]
    second = create(pg_factory, actor, designer, 'two')[1]
    material_id, store = ready(pg_factory, actor)
    barrier = Barrier(2)
    def action(operation):
        with pg_factory() as session:
            user = session.get(Member, actor)
            barrier.wait(timeout=8)
            try:
                if operation == 'delete':
                    files.delete(session, store, user, material_id)
                elif operation == 'retry':
                    files.retry(session, store, user, material_id)
                else:
                    task = first if operation == 'first' else second
                    service.submit(session, user, UUID(task['id']),
                                   SubmitMaterials(materialIds=[material_id], version=1), operation)
                return 200
            except HTTPException as exc:
                return exc.status_code
    with ThreadPoolExecutor(2) as pool:
        futures = [pool.submit(action, operation) for operation in ('first', other)]
        outcomes = [future.result(timeout=30) for future in futures]
    assert 200 in outcomes
    with pg_factory() as session:
        record = session.get(Material, material_id)
        if record.task_id:
            assert record.deleted_at is None and record.object_key in store.data
        else:
            assert other == 'delete' and record.deleted_at is not None
    if other != 'retry':
        assert sorted(outcomes) in ([200, 404], [200, 409])
