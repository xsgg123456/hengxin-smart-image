"""Archive access follows successful assignments and survives deletion with exact bytes."""
from io import BytesIO
from uuid import UUID
from zipfile import ZipFile
import pytest
from app.overseas.auth.models import Member
from app.overseas.archives.models import Archive
from app.overseas.tasks.cleanup import cleanup_once
from test_overseas_auth import login, MEMBER
from test_overseas_tasks import overseas, add_member, ROOT
from test_overseas_materials import materials
from test_overseas_studio import studio
from test_overseas_task_deletion import deletion, generated, archived, request
from test_overseas_assignment import assign


def become(overseas, identity):
    client, factory, assertion = overseas
    with factory() as session:
        member = session.get(Member, identity)
        assertion['member'] = {**MEMBER, 'provider_user_id': member.provider_user_id,
                               'name': member.name}
    assert login(client).status_code == 200


def accessible(client, archive, expected_bytes, deleted=False):
    assert client.get(ROOT + '/archives').json()['total'] == 1
    response = client.get(ROOT + '/archives/' + archive['id'])
    assert response.status_code == 200, response.text
    view = response.json()
    assert view['sourceDeleted'] is deleted
    assert [client.get(row['url']).content for row in view['pictures']] == expected_bytes
    zipped = client.get(ROOT + '/archives/' + archive['id'] + '/download')
    assert zipped.status_code == 200
    with ZipFile(BytesIO(zipped.content)) as bundle:
        assert [bundle.read(name) for name in bundle.namelist()] == expected_bytes
    return [row['url'] for row in view['pictures']]


def denied(client, archive, picture_urls):
    assert client.get(ROOT + '/archives').json()['total'] == 0
    for suffix in ('', '/download'):
        assert client.get(ROOT + '/archives/' + archive['id'] + suffix).status_code == 403
    assert all(client.get(url).status_code == 403 for url in picture_urls)


def test_assignment_moves_all_archive_access_and_deletion_preserves_last_designer(deletion, overseas):
    client, factory, admin, task, _, store = deletion
    original, replacement, final = UUID(task['designer']['id']), add_member(factory), add_member(factory)
    rows = generated(deletion)
    expected = [store.data[row['object_key']] for row in rows]
    archive = archived(deletion, rows)
    become(overseas, original)
    urls = accessible(client, archive, expected)
    become(overseas, admin)
    version = client.get(ROOT + '/tasks/' + task['id']).json()['version']
    assert assign(client, task['id'], replacement, version).status_code == 200
    assert assign(client, task['id'], final, version + 1, 'final').status_code == 200
    # Replaying an earlier successful request must not restore the earlier assignee.
    assert assign(client, task['id'], replacement, version).status_code == 200
    for identity in (original, replacement):
        become(overseas, identity)
        denied(client, archive, urls)
    become(overseas, final)
    assert client.get(ROOT + '/tasks/' + task['id']).status_code == 200
    accessible(client, archive, expected)
    become(overseas, admin)
    assert request(client, task).json()['status'] == 'deleting'
    assert cleanup_once(factory, store) == 1
    accessible(client, archive, expected, deleted=True)
    for identity in (original, replacement):
        become(overseas, identity)
        denied(client, archive, urls)
    become(overseas, final)
    assert client.get(ROOT + '/tasks/' + task['id']).status_code == 404
    accessible(client, archive, expected, deleted=True)


def test_assignment_failure_rolls_back_archive_permissions(deletion, overseas, monkeypatch):
    from app.overseas.tasks import assignment
    client, factory, _, task, _, store = deletion
    rows = generated(deletion)
    expected = [store.data[row['object_key']] for row in rows]
    archive = archived(deletion, rows)
    original, replacement = UUID(task['designer']['id']), add_member(factory)
    version = client.get(ROOT + '/tasks/' + task['id']).json()['version']
    original_record = assignment.request_record

    def fail(*args):
        original_record(*args)
        args[0].flush()
        raise RuntimeError('injected assignment failure')

    monkeypatch.setattr(assignment, 'request_record', fail)
    with pytest.raises(RuntimeError, match='injected'):
        assign(client, task['id'], replacement, version)
    with factory() as session:
        assert session.get(Archive, UUID(archive['id'])).designer_id == original
    assert client.get(ROOT + '/tasks/' + task['id']).json()['version'] == version
    become(overseas, original)
    urls = accessible(client, archive, expected)
    become(overseas, replacement)
    denied(client, archive, urls)
