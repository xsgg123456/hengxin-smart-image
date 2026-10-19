"""HTTP authorization, durable retries, physical erasure and source isolation."""
from uuid import UUID
import pytest
from sqlalchemy import select, func
from app.overseas.archives.models import Archive, ArchiveAsset, ArchiveEvent, ArchiveDeletion
from app.overseas.archives.cleanup import cleanup_once
from app.overseas.tasks.cleanup import cleanup_once as cleanup_tasks
from app.overseas.tasks.models import Task
from app.overseas.studio.models import Picture
from test_overseas_task_deletion import deletion, generated, archived, request as delete_task
from test_overseas_studio import studio
from test_overseas_materials import materials
from test_overseas_tasks import overseas, ROOT, HEADERS
from test_overseas_assignment import change_roles
from test_overseas_plans import post


def remove(client, archive, token=None, headers=HEADERS):
    return client.request('DELETE', ROOT + '/archives/' + archive['id'],
        json={'deleteToken': token or archive['deleteToken']}, headers=headers)


@pytest.mark.parametrize('broken', ['missing', 'corrupt', 'missing_asset'])
def test_delete_confirmation_does_not_require_healthy_images(deletion, broken, monkeypatch):
    client, factory, actor, task, _, store = deletion
    archive = archived(deletion, generated(deletion))
    assert delete_task(client, task).status_code == 200
    assert cleanup_tasks(factory, store) == 1
    with factory.begin() as session:
        asset = session.scalar(select(ArchiveAsset))
        if broken == 'missing':
            store.data.pop(asset.object_key)
        elif broken == 'corrupt':
            store.data[asset.object_key] = b'corrupt image'
        else:
            session.delete(asset)
    # Latest confirmation must never touch storage, even for an old deleted source.
    monkeypatch.setattr(store, 'open', lambda _: (_ for _ in ()).throw(AssertionError('preview read image')))
    path = ROOT + '/archives/' + archive['id'] + '/deletion-preview'
    response = client.get(path)
    assert response.status_code == 200
    confirmation = response.json()
    assert confirmation['pictureCount'] == 2 and len(confirmation['deleteToken']) == 64
    assert 'pictures' not in confirmation
    assert remove(client, confirmation).status_code == 200
    assert cleanup_once(factory, store) == 1
    assert not any('/' + archive['id'] + '/' in key for key in store.data)
    change_roles(factory, actor, ('designer',))
    assert client.get(path).status_code == 403


@pytest.mark.parametrize('source_deleted', [False, True])
def test_real_erasure_preserves_source_and_rearchive(deletion, source_deleted):
    client, factory, _, task, _, store = deletion
    rows = generated(deletion)
    archive = archived(deletion, rows)
    url = ROOT + '/archives/' + archive['id']
    if source_deleted:
        assert delete_task(client, task).status_code == 200
        assert cleanup_tasks(factory, store) == 1
    archive = client.get(url).json()
    picture_url = archive['pictures'][0]['url']
    owned = [key for key in store.data if '/' + archive['id'] + '/' in key]
    orphan = owned[0].rsplit('/', 1)[0] + '/orphan'
    store.data[orphan], store.buckets[orphan] = b'orphan', store.buckets[owned[0]]
    store.data['shared/credential'] = b'keep'
    assert remove(client, archive).json()['status'] == 'deleting'
    assert all(key in store.data for key in owned)
    assert remove(client, archive).json()['status'] == 'deleting'
    assert client.get(url).json()['deletionStatus'] == 'deleting'
    assert client.get(picture_url).status_code == 409
    assert client.get(url + '/download').status_code == 409
    if not source_deleted:
        assert post(client, task, '/studio/archive', dict(pictureIds=[rows[0]['id']], sku='A'), 'late').status_code == 409
    assert cleanup_once(factory, store) == 1
    assert cleanup_once(factory, store) == 0
    assert all(key not in store.data for key in [*owned, orphan])
    assert store.data['shared/credential'] == b'keep'
    assert client.get(url).status_code == 404
    assert client.get(ROOT + '/archives').json()['total'] == 0
    assert client.get(url + '/deletion').json()['status'] == 'deleted'
    assert remove(client, archive).json()['status'] == 'deleted'
    with factory() as session:
        for model in (Archive, ArchiveAsset, ArchiveEvent):
            assert session.scalar(select(func.count()).select_from(model)) == 0
        receipt = session.get(ArchiveDeletion, UUID(archive['id']))
        assert receipt.error is None
        if not source_deleted:
            assert session.get(Task, UUID(task['id'])) is not None
            assert all(session.get(Picture, UUID(row['id'])).sku is None for row in rows)
    if not source_deleted:
        assert all(row['object_key'] in store.data for row in rows)
        body = dict(pictureIds=[row['id'] for row in rows], sku='A')
        assert post(client, task, '/studio/archive', body, 'archive').status_code == 409
        assert post(client, task, '/studio/archive', body, 'new-key').status_code == 200
        assert client.get(ROOT + '/archives').json()['items'][0]['id'] != archive['id']


def test_failure_partial_retry_and_task_wait(deletion, monkeypatch):
    client, factory, _, task, _, store = deletion
    archive = archived(deletion, generated(deletion))
    assert remove(client, archive).status_code == 200
    original = store.remove
    removed = []
    def partial(row):
        if removed:
            raise RuntimeError('secret path must not leak')
        original(row)
        removed.append(row.object_key)
    monkeypatch.setattr(store, 'remove', partial)
    assert cleanup_once(factory, store) == 0
    view = client.get(ROOT + '/archives/' + archive['id']).json()
    assert view['deletionStatus'] == 'delete_failed' and 'secret' not in view['deletionError']
    assert delete_task(client, task).status_code == 200
    assert cleanup_tasks(factory, store) == 0
    assert client.get(ROOT + '/tasks/' + task['id']).status_code == 200
    monkeypatch.setattr(store, 'remove', original)
    assert remove(client, view).json()['status'] == 'deleting'
    assert cleanup_once(factory, store) == 1
    assert cleanup_tasks(factory, store) == 1


@pytest.mark.parametrize('role', ['operator', 'operator_manager', 'designer', 'design_manager'])
def test_non_admin_cannot_delete_or_poll(deletion, role):
    client, factory, actor, _, _, store = deletion
    archive = archived(deletion, generated(deletion))
    before = dict(store.data)
    change_roles(factory, actor, (role,))
    assert remove(client, archive).status_code == 403
    assert client.get(ROOT + '/archives/' + archive['id'] + '/deletion').status_code == 403
    assert before == store.data
    with factory() as session:
        assert session.get(ArchiveDeletion, UUID(archive['id'])) is None


@pytest.mark.parametrize('changed', ['asset', 'event', 'versions'])
def test_same_count_content_change_invalidates_confirmation(deletion, changed):
    client, factory, _, _, _, store = deletion
    archive = archived(deletion, generated(deletion))
    with factory.begin() as session:
        if changed == 'asset':
            session.scalar(select(ArchiveAsset)).name = 'new name.png'
        elif changed == 'event':
            session.scalar(select(ArchiveEvent)).actor_name = 'new name'
        else:
            record = session.scalar(select(Archive))
            record.versions = list(reversed(record.versions))
    assert remove(client, archive).status_code == 409
    assert cleanup_once(factory, store) == 0


def test_browser_token_and_snapshot_validation(deletion):
    client, _, _, _, _, _ = deletion
    archive = archived(deletion, generated(deletion))
    assert remove(client, archive, headers={}).status_code == 403
    assert remove(client, archive, token='invalid').status_code == 422
    assert remove(client, archive, token='0' * 64).status_code == 409


@pytest.mark.parametrize('unsafe', ['shared/key', 'other_archive', 'source_reference'])
def test_unsafe_and_shared_objects_fail_without_deleting(deletion, unsafe):
    client, factory, _, _, _, store = deletion
    rows = generated(deletion)
    archive = archived(deletion, rows)
    with factory.begin() as session:
        asset = session.scalar(select(ArchiveAsset))
        if unsafe == 'source_reference':
            session.get(Picture, UUID(rows[0]['id'])).object_key = asset.object_key
        elif unsafe == 'other_archive':
            asset.object_key = asset.object_key.replace(archive['id'], str(UUID(int=1)))
        else:
            asset.object_key = unsafe
    # List is metadata-only and allows confirming malformed archives for a safe failed cleanup.
    archive = client.get(ROOT + '/archives').json()['items'][0]
    before = dict(store.data)
    assert remove(client, archive).status_code == 200
    assert cleanup_once(factory, store) == 0
    assert store.data == before


def test_completed_studio_requires_explicit_reopen_after_erasure(deletion):
    client, factory, _, task, _, store = deletion
    rows = generated(deletion)
    archive = archived(deletion, rows)
    assert post(client, task, '/studio/complete', {'version': 2}, 'complete').status_code == 200
    assert client.get(ROOT + '/tasks/' + task['id']).json()['status'] == 'completed'
    assert remove(client, archive).status_code == 200
    assert cleanup_once(factory, store) == 1
    assert client.get(ROOT + '/tasks/' + task['id']).json()['status'] == 'completed'
    replay = post(client, task, '/studio/complete', {'version': 2}, 'complete')
    assert replay.status_code == 200 and replay.json()['archiveId'] is None
    assert post(client, task, '/studio/reopen', {'version': 4}, 'reopen').status_code == 200
    assert post(client, task, '/studio/complete', {'version': 5}, 'complete-again').status_code == 409
    assert post(client, task, '/studio/archive', dict(pictureIds=[rows[0]['id']], sku='A'), 'new').status_code == 200


def test_legacy_rearchive_and_old_idempotency_key_conflict(materials, monkeypatch):
    from test_overseas_archive_audit import test_legacy_whole_set_archive_records_actor_and_replays_once
    test_legacy_whole_set_archive_records_actor_and_replays_once(materials, monkeypatch)
    client, factory, _, _, store = materials
    archive = client.get(ROOT + '/archives').json()['items'][0]
    task = client.get(ROOT + '/tasks/' + archive['taskId']).json()
    assert remove(client, archive).status_code == 200
    assert cleanup_once(factory, store) == 1
    current = client.get(ROOT + '/tasks/' + task['id']).json()
    assert current['status'] == 'generating'
    assert post(client, task, '/archive', {'version': task['version'] - 1}, 'legacy').status_code == 409
    assert post(client, task, '/archive', {'version': current['version']}, 'new').status_code == 200


def test_sql_failure_after_erasure_never_reprotects_and_retries(deletion, monkeypatch):
    from app.overseas.archives import cleanup
    client, factory, _, _, _, store = deletion
    archive = archived(deletion, generated(deletion))
    assert remove(client, archive).status_code == 200
    original = cleanup.erase_records
    def fail(*args):
        raise RuntimeError('injected SQL failure')
    monkeypatch.setattr(cleanup, 'erase_records', fail)
    assert cleanup_once(factory, store) == 0
    assert not any('/' + archive['id'] + '/' in key for key in store.data)
    view = client.get(ROOT + '/archives/' + archive['id']).json()
    assert view['deletionStatus'] == 'delete_failed'
    assert not any('/' + archive['id'] + '/' in key for key in store.data)
    monkeypatch.setattr(cleanup, 'erase_records', original)
    assert remove(client, view).status_code == 200
    assert cleanup_once(factory, store) == 1


def test_noop_storage_removal_does_not_report_success(deletion, monkeypatch):
    client, factory, _, _, _, store = deletion
    archive = archived(deletion, generated(deletion))
    assert remove(client, archive).status_code == 200
    monkeypatch.setattr(store, 'remove', lambda row: None)
    assert cleanup_once(factory, store) == 0
    assert client.get(ROOT + '/archives/' + archive['id'] + '/deletion').json()['status'] == 'delete_failed'


def test_other_archive_bytes_and_records_survive(deletion):
    from uuid import uuid4
    from app.overseas.studio.files import read
    client, factory, _, _, _, store = deletion
    archive = archived(deletion, generated(deletion))
    with factory.begin() as session:
        original = session.scalar(select(Archive))
        other = Archive(id=uuid4(), task_id=None, **{name: getattr(original, name) for name in
            ('versions', 'product_name', 'brand', 'platform', 'skus', 'sku_search', 'created_by', 'designer_id')})
        session.add(other)
        session.flush()
        for row in session.scalars(select(ArchiveAsset).where(ArchiveAsset.archive_id == original.id)):
            copied = ArchiveAsset(id=uuid4(), archive_id=other.id, object_key=f'archives/{uuid4()}/{other.id}/{uuid4()}',
                **{name: getattr(row, name) for name in ('source_version', 'position', 'sku', 'name',
                    'content_type', 'size_bytes', 'checksum', 'width', 'height', 'bucket')})
            store.put(copied, read(store, row))
            session.add(copied)
        other_id = other.id
    before = {key: value for key, value in store.data.items() if '/' + str(other_id) + '/' in key}
    assert remove(client, archive).status_code == 200
    assert cleanup_once(factory, store) == 1
    assert all(store.data[key] == value for key, value in before.items())
    view = client.get(ROOT + '/archives/' + str(other_id)).json()
    assert len(view['pictures']) == 2
    assert all(client.get(row['url']).status_code == 200 for row in view['pictures'])
