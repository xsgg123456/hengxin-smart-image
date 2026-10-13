from hashlib import sha256
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4
from zipfile import ZipFile
import pytest
from sqlalchemy import select
from app.core.config import get_settings
from app.overseas.tasks.cleanup import cleanup_once
from app.overseas.tasks.models import Task, ExecutionObject
from app.overseas.execution.models import Job
from app.overseas.execution import claims, objects
from app.overseas.plans.models import Plan
from app.overseas.pictures.models import Picture, PictureVersion
from test_overseas_task_deletion import deletion, request, generated, archived
from test_overseas_studio import studio, output, send
from test_overseas_materials import materials
from test_overseas_tasks import overseas, ROOT
from test_overseas_plans import post
from test_overseas_tasks import add_member
from test_overseas_assignment import assign
from test_overseas_archive_assignment import become


@pytest.mark.parametrize('with_archive', [False, True])
def test_legacy_all_versions_all_attempt_directories_are_erased(deletion, overseas, with_archive):
    client, factory, _, task, _, store = deletion
    task_id = UUID(task['id'])
    expected = []
    with factory.begin() as session:
        current = session.get(Task, task_id)
        current.workflow, current.status = 'legacy', 'review'
        job = Job(task_id=task_id, kind='generation', dedupe_key='legacy', payload={},
            status='succeeded', execution_count=1, process_exited=True)
        session.add(job)
        session.flush()
        plan = Plan(task_id=task_id, job_id=job.id, version=1, status='confirmed')
        session.add(plan)
        session.flush()
        picture = Picture(task_id=task_id, plan_id=plan.id, job_id=job.id, sku='A', position=0,
            title='旧图片', version=2, approved_version=2)
        session.add(picture)
        session.flush()
        for number in (1, 2):
            data = output(store)
            old = data.pop('id')
            old_key = data['object_key']
            data['object_key'] = f'pictures/{job.id}/{old}'
            raw = store.data.pop(old_key)
            store.put(SimpleNamespace(**data), raw)
            session.add(PictureVersion(**data, picture_id=picture.id, job_id=job.id, version=number))
            if number == 2:
                expected.append(sha256(raw).hexdigest())
        job_id = job.id
    private = Path(get_settings().codex_execution_root) / str(job_id)
    for attempt in [uuid4(), uuid4()]:
        path = private / 'rounds' / str(attempt)
        path.mkdir(parents=True)
        (path / 'private.txt').write_text('private input and context')
    archive = None
    if with_archive:
        response = post(client, task, '/archive', {'version': 2}, 'legacy-archive')
        assert response.status_code == 200, response.text
        archive = client.get(ROOT + '/archives').json()['items'][0]
        replacement = add_member(factory)
        version = client.get(ROOT + '/tasks/' + task['id']).json()['version']
        assert assign(client, task['id'], replacement, version).status_code == 200
    request(client, task)
    assert cleanup_once(factory, store) == 1
    assert not private.exists()
    with factory() as session:
        assert session.scalar(select(PictureVersion)) is None
        assert session.scalar(select(Picture)) is None
        assert session.scalar(select(Plan)) is None
        assert session.scalar(select(Job)) is None
    if archive:
        become(overseas, UUID(task['designer']['id']))
        assert client.get(ROOT + '/archives/' + archive['id'] + '/download').status_code == 403
        become(overseas, replacement)
        response = client.get(ROOT + '/archives/' + archive['id'] + '/download')
        assert response.status_code == 200
        with ZipFile(BytesIO(response.content)) as bundle:
            assert [sha256(bundle.read(name)).hexdigest() for name in bundle.namelist()] == expected


def test_sql_rollback_orphan_namespaces_are_owned_and_successful_archives_excluded(deletion):
    client, factory, _, task, _, store = deletion
    rows = generated(deletion, 1)
    archive = archived(deletion, rows)
    bucket = get_settings().minio_bucket
    prefixes = [f'studio/uploads/{task["id"]}/', f'studio/pictures/{task["id"]}/',
                f'archives/{task["id"]}/{uuid4()}/']
    orphan_keys = [prefix + str(uuid4()) for prefix in prefixes]
    unrelated = f'studio/uploads/{uuid4()}/{uuid4()}'
    for key in orphan_keys + [unrelated]:
        store.put(SimpleNamespace(bucket=bucket, object_key=key), b'orphan')
    request(client, task)
    assert cleanup_once(factory, store) == 1
    assert all(key not in store.data for key in orphan_keys)
    assert store.data[unrelated] == b'orphan'
    assert client.get(ROOT + '/archives/' + archive['id'] + '/download').status_code == 200


def test_collector_write_ahead_receipt_cleans_ambiguous_storage_success(deletion, monkeypatch):
    client, factory, _, task, _, store = deletion
    turn = send(client, task).json()['turns'][0]
    job_id = UUID(turn['jobId'])
    token = claims.claim(factory, job_id)
    with factory() as session:
        job = session.get(Job, job_id)
        session.expunge(job)
    row = dict(bucket=get_settings().minio_bucket, object_key=f'studio/pictures/{uuid4()}')
    original = store.put
    def uncertain(record, data):
        original(record, data)
        raise OSError('response lost after successful storage')
    monkeypatch.setattr(store, 'put', uncertain)
    with objects.collecting(factory, job, token), pytest.raises(OSError):
        objects.put(store, row, b'late output')
    with factory() as session:
        assert session.scalar(select(ExecutionObject)).object_key == row['object_key']
    request(client, task)
    monkeypatch.setattr(store, 'put', original)
    with objects.collecting(factory, job, token), pytest.raises(Exception):
        objects.put(store, {**row, 'object_key': f'studio/pictures/{uuid4()}'}, b'must not write')
    with factory.begin() as session:
        current = claims.locked_job(session, job_id)
        current.process_exited = True
        claims.end(session, current, 'cancelled')
    assert cleanup_once(factory, store) == 1
    assert row['object_key'] not in store.data
    with factory() as session:
        assert session.scalar(select(ExecutionObject)) is None
