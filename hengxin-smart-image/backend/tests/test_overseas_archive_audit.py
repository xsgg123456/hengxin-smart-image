"""Authenticated confirmations, transactional failures and deletion-safe history."""
from uuid import UUID
import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select, func
from app.overseas.archives.models import Archive, ArchiveAsset, ArchiveEvent
from app.overseas.auth.models import BusinessSession, Member
from app.overseas.studio.models import Picture
from app.overseas.tasks.models import TaskRequest
from app.overseas.tasks.cleanup import cleanup_once
from test_overseas_task_deletion import deletion, generated, archived, request
from test_overseas_studio import studio
from test_overseas_materials import materials
from test_overseas_tasks import overseas, ROOT, add_member
from test_overseas_assignment import change_roles
from test_overseas_plans import post


def test_actor_snapshot_multiple_confirmations_and_replay(deletion):
    client, factory, creator, task, _, _ = deletion
    rows = generated(deletion)
    actual = add_member(factory, ('super_admin',), name='实际归档人')
    with factory.begin() as session:
        session.scalar(select(BusinessSession)).user_id = actual
    archive = archived(deletion, rows[:1])
    first = archive['latestArchive']
    assert first['actorId'] == str(actual) != str(creator)
    assert first['actorName'] == '实际归档人' and first['at'].endswith(('+00:00', 'Z'))
    assert len(first['pictures']) == 1 and first['pictures'][0]['sku'] == 'A'
    body = dict(pictureIds=[rows[0]['id']], sku='A')
    assert post(client, task, '/studio/archive', body, 'archive').status_code == 200
    assert post(client, task, '/studio/archive', {**body, 'sku': 'B'}, 'archive').status_code == 409
    with factory.begin() as session:
        session.get(Member, actual).name = '已改名'
        session.scalar(select(BusinessSession)).user_id = creator
        assert session.scalar(select(Archive)).created_by == creator
    assert post(client, task, '/studio/archive', dict(pictureIds=[rows[1]['id']], sku='B'), 'second').status_code == 200
    view = client.get(ROOT + '/archives/' + archive['id']).json()
    assert len(view['archiveHistory']) == 2 and not view['historyIncomplete']
    assert view['archiveHistory'][1] == first
    assert view['latestArchive']['actorId'] == str(creator)
    assert view['latestArchive']['pictures'][0]['sku'] == 'B'
    assert client.get(ROOT + '/archives').json()['items'][0]['latestArchive'] == view['latestArchive']
    assert request(client, task).status_code == 200
    assert cleanup_once(factory, deletion[-1]) == 1
    after = client.get(ROOT + '/archives/' + archive['id']).json()
    assert after['sourceDeleted'] and after['archiveHistory'] == view['archiveHistory']
    change_roles(factory, creator, ('designer',))
    assert client.get(ROOT + '/archives').json()['items'] == []
    assert client.get(ROOT + '/archives/' + archive['id']).status_code == 403


def test_unknown_history_stays_explicit_after_new_confirmation(deletion):
    client, factory, _, task, _, _ = deletion
    rows = generated(deletion)
    archive = archived(deletion, rows[:1])
    with factory.begin() as session:
        session.execute(delete(ArchiveEvent))
    view = client.get(ROOT + '/archives/' + archive['id']).json()
    assert view['latestArchive'] is None and view['archiveHistory'] == [] and view['historyIncomplete']
    assert post(client, task, '/studio/archive', dict(pictureIds=[rows[1]['id']], sku='B'), 'new').status_code == 200
    view = client.get(ROOT + '/archives/' + archive['id']).json()
    assert len(view['archiveHistory']) == 1 and view['historyIncomplete']


@pytest.mark.parametrize('stage', ['storage', 'audit', 'finish'])
def test_failure_rolls_back_confirmation_sku_archive_and_request(deletion, monkeypatch, stage):
    from app.overseas.archives import audit
    from app.overseas.studio import service
    client, factory, _, task, _, store = deletion
    rows = generated(deletion)
    def fail(*args, **kwargs):
        raise HTTPException(503, 'injected failure')
    if stage == 'storage':
        monkeypatch.setattr(store, 'put', fail)
    elif stage == 'audit':
        original = audit.record_confirmation
        def fail_after_insert(*args, **kwargs):
            original(*args, **kwargs)
            fail()
        monkeypatch.setattr(audit, 'record_confirmation', fail_after_insert)
    else:
        monkeypatch.setattr(service, 'finish', fail)
    assert post(client, task, '/studio/archive', dict(pictureIds=[rows[0]['id']], sku='A'), 'failure').status_code == 503
    with factory() as session:
        for model in (Archive, ArchiveAsset, ArchiveEvent):
            assert session.scalar(select(func.count()).select_from(model)) == 0
        assert session.get(Picture, UUID(rows[0]['id'])).sku is None
        assert session.scalar(select(TaskRequest).where(TaskRequest.operation == 'studio_archive')) is None


def test_invalid_or_unauthorized_confirmation_never_writes_audit(deletion):
    client, factory, actor, task, _, _ = deletion
    rows = generated(deletion)
    body = dict(pictureIds=[rows[0]['id']], sku='not-a-task-sku')
    assert post(client, task, '/studio/archive', body, 'invalid').status_code == 422
    assert post(client, task, '/studio/archive', {**body, 'sku': 'A', 'actorName': '伪造'}, 'spoof').status_code == 422
    change_roles(factory, actor, ('operator',))
    assert post(client, task, '/studio/archive', {**body, 'sku': 'A'}, 'denied').status_code == 403
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(ArchiveEvent)) == 0


def test_failed_append_preserves_previous_history_and_snapshot(deletion, monkeypatch):
    from app.overseas.studio import service
    client, factory, _, task, _, _ = deletion
    rows = generated(deletion)
    archive = archived(deletion, rows[:1])
    before = client.get(ROOT + '/archives/' + archive['id']).json()
    def fail(*args, **kwargs):
        raise HTTPException(503, 'injected failure after audit')
    monkeypatch.setattr(service, 'finish', fail)
    assert post(client, task, '/studio/archive', dict(pictureIds=[rows[1]['id']], sku='B'), 'failure').status_code == 503
    assert client.get(ROOT + '/archives/' + archive['id']).json() == before
    with factory() as session:
        assert session.get(Picture, UUID(rows[1]['id'])).sku is None


def test_legacy_whole_set_archive_records_actor_and_replays_once(materials, monkeypatch):
    from test_overseas_pictures import confirmed, picture_list, action
    from test_overseas_studio import output
    from app.overseas.pictures.models import Picture as LegacyPicture, PictureVersion
    from app.overseas.execution.models import Job
    client, factory, actor, task = confirmed(materials, monkeypatch)
    # Archive contract starts with completed, byte-backed versions; generation is separate.
    with factory.begin() as session:
        for picture in session.scalars(select(LegacyPicture)):
            artifact = output(materials[-1])
            artifact['id'] = UUID(artifact['id'])
            session.add(PictureVersion(**artifact, picture_id=picture.id, job_id=picture.job_id, version=1))
            picture.version = 1
            session.get(Job, picture.job_id).status = 'succeeded'
    for picture in picture_list(client, task)['items']:
        version = picture_list(client, task)['taskVersion']
        assert action(client, picture, '/approve', version, 'approve-' + picture['id']).status_code == 200
    body = {'version': picture_list(client, task)['taskVersion']}
    for _ in range(2):
        assert post(client, task, '/archive', body, 'legacy').status_code == 200
    archive = client.get(ROOT + '/archives').json()['items'][0]
    view = client.get(ROOT + '/archives/' + archive['id']).json()
    assert len(view['archiveHistory']) == 1 and not view['historyIncomplete']
    assert view['latestArchive']['actorId'] == str(actor)
    assert {p['sku'] for p in view['latestArchive']['pictures']} == {'A', 'B'}
