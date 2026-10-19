"""Versioned lifecycle via real HTTP/SQL, without model calls."""
from uuid import UUID
import pytest
from sqlalchemy import select, func, delete
from app.overseas.archives.models import Archive, ArchiveAsset, ArchiveDeletion
from app.overseas.execution.models import Job
from app.overseas.studio.models import Conversation, Turn
from app.overseas.tasks.models import Task, TaskEvent, TaskOutbox, TaskRequest, TaskDeletion
from test_overseas_studio import studio, send, finish, output
from test_overseas_materials import materials
from test_overseas_tasks import overseas, ROOT, HEADERS
from test_overseas_assignment import change_roles
from test_overseas_plans import post


def view(client, task):
    return client.get(ROOT + '/tasks/' + task['id'] + '/studio').json()


def save_archive(studio):
    client, factory, _, task, _, store = studio
    first = send(client, task).json()['turns'][0]
    image = output(store)
    finish(factory, first, [image])
    result = post(client, task, '/studio/archive', {'pictureIds': [image['id']], 'sku': 'A'}, 'archive')
    assert result.status_code == 200, result.text
    return result.json()


def transition(client, task, operation, version, key=None):
    return post(client, task, '/studio/' + operation, {'version': version}, key or operation)


def test_lifecycle_replays_across_cycles_without_repeating_audits(studio):
    client, factory, actor, task, _, store = studio
    original = save_archive(studio)
    assert original['taskVersion'] == 2 and not original['reopened']
    assert original['archiveId'] == client.get(ROOT + '/archives').json()['items'][0]['id']
    objects = dict(store.data)
    complete = transition(client, task, 'complete', 2)
    assert complete.status_code == 200 and complete.json()['completed']
    assert complete.json()['taskVersion'] == 3
    assert transition(client, task, 'complete', 2).json() == complete.json()
    assert transition(client, task, 'reopen', 2, 'stale').status_code == 409
    reopened = transition(client, task, 'reopen', 3)
    assert reopened.status_code == 200 and not reopened.json()['completed']
    assert reopened.json()['taskVersion'] == 4 and reopened.json()['reopened']
    assert transition(client, task, 'reopen', 3).json() == reopened.json()
    assert transition(client, task, 'complete', 2).json() == reopened.json()
    assert transition(client, task, 'complete', 2, 'stale').status_code == 409
    for field in ('conversationId', 'turns', 'materials', 'archiveId'):
        assert reopened.json()[field] == original[field]
    again = transition(client, task, 'complete', 4, 'complete-again')
    assert again.status_code == 200 and again.json()['taskVersion'] == 5
    assert transition(client, task, 'reopen', 3).json() == again.json()
    assert transition(client, task, 'reopen', 4, 'stale-again').status_code == 409
    # Reusing a successful key with a new version is a fingerprint conflict.
    assert transition(client, task, 'reopen', 5).status_code == 409
    assert transition(client, task, 'reopen', 5, 'reopen-again').status_code == 200
    assert store.data == objects
    with factory() as session:
        events = list(session.scalars(select(TaskEvent).where(
            TaskEvent.kind.in_(('task.studio_completed', 'task.studio_reopened'))).order_by(TaskEvent.version)))
        assert [event.version for event in events] == [3, 4, 5, 6]
        assert [event.title for event in events] == ['完成工作台任务', '解冻工作台'] * 2
        assert all(event.actor_id == actor and event.actor_name == '海外成员' and event.created_at for event in events)
        assert session.scalar(select(func.count()).select_from(TaskOutbox).where(
            TaskOutbox.event_id.in_([event.id for event in events]))) == 4
        assert session.scalar(select(func.count()).select_from(Job)) == 1
        assert session.scalar(select(func.count()).select_from(Conversation)) == 1
        assert session.scalar(select(Conversation)).session_id == 'thread-1'
    detail = client.get(ROOT + '/tasks/' + task['id']).json()
    assert detail['status'] == 'studio' and detail['version'] == 6
    assert [event['version'] for event in detail['events']][-4:] == [3, 4, 5, 6]


@pytest.mark.parametrize('operation', ['complete', 'reopen'])
@pytest.mark.parametrize('body', [{}, {'version': 0}, {'version': -1}, {'version': True},
    {'version': '2'}, {'version': 2.5}, {'version': None}, {'version': 2, 'extra': True}])
def test_lifecycle_requires_strict_positive_version(studio, operation, body):
    client, _, _, task, _, _ = studio
    assert post(client, task, '/studio/' + operation, body).status_code == 422
    assert view(client, task)['taskVersion'] == 2


@pytest.mark.parametrize('role,assigned,expected', [
    ('operator', True, 403), ('operator_manager', True, 403), ('designer', False, 403),
    ('designer', True, 200), ('design_manager', False, 200)])
def test_reopen_obeys_role_and_current_assignment(studio, role, assigned, expected):
    client, factory, actor, task, _, _ = studio
    save_archive(studio)
    assert transition(client, task, 'complete', 2).status_code == 200
    if assigned:
        with factory.begin() as session:
            session.get(Task, UUID(task['id'])).designer_id = actor
    change_roles(factory, actor, (role,))
    response = transition(client, task, 'reopen', 3)
    assert response.status_code == expected, response.text
    with factory() as session:
        assert session.get(Task, UUID(task['id'])).version == (4 if expected == 200 else 3)


def test_permission_is_rechecked_before_replay_after_reassignment(studio):
    client, factory, actor, task, _, _ = studio
    save_archive(studio)
    transition(client, task, 'complete', 2)
    original_designer = UUID(task['designer']['id'])
    with factory.begin() as session:
        session.get(Task, UUID(task['id'])).designer_id = actor
    change_roles(factory, actor, ('designer',))
    assert transition(client, task, 'reopen', 3).status_code == 200
    with factory.begin() as session:
        session.get(Task, UUID(task['id'])).designer_id = original_designer
    assert transition(client, task, 'reopen', 3).status_code == 403


@pytest.mark.parametrize('invalid', ['unapproved', 'legacy', 'studio', 'deleting', 'delete_failed', 'deleted'])
def test_invalid_task_cannot_reopen(studio, invalid):
    client, factory, actor, task, _, _ = studio
    with factory.begin() as session:
        row = session.get(Task, UUID(task['id']))
        row.status = 'completed'
        if invalid == 'unapproved':
            row.requirements_approved = False
        elif invalid == 'legacy':
            row.workflow = 'legacy'
        elif invalid == 'studio':
            row.status = 'studio'
        else:
            session.add(TaskDeletion(task_id=row.id, actor_id=actor, status=invalid))
    assert transition(client, task, 'reopen', 2).status_code == 409


@pytest.mark.parametrize('operation', ['complete', 'reopen'])
@pytest.mark.parametrize('status', ['queued', 'running', 'collecting', 'cancelling', 'uncertain'])
def test_any_active_job_blocks_lifecycle(studio, operation, status):
    client, factory, _, task, _, _ = studio
    save_archive(studio)
    if operation == 'reopen':
        assert transition(client, task, 'complete', 2).status_code == 200
    with factory.begin() as session:
        session.scalar(select(Job)).status = status
    assert transition(client, task, operation, 3 if operation == 'reopen' else 2).status_code == 409


@pytest.mark.parametrize('invalid', ['missing', 'empty', 'missing_asset', 'deleting', 'delete_failed'])
def test_no_usable_archive_does_not_complete_but_allows_reopen(studio, invalid):
    client, factory, _, task, _, _ = studio
    save_archive(studio)
    with factory.begin() as session:
        record = session.scalar(select(Archive))
        if invalid == 'empty':
            record.versions = []
        elif invalid == 'missing_asset':
            session.execute(delete(ArchiveAsset))
        elif invalid == 'missing':
            record.task_id = None
        else:
            session.add(ArchiveDeletion(archive_id=record.id, status=invalid))
    assert view(client, task)['archiveId'] is None
    assert transition(client, task, 'complete', 2).status_code == 409
    with factory.begin() as session:
        session.get(Task, UUID(task['id'])).status = 'completed'
    response = transition(client, task, 'reopen', 2)
    assert response.status_code == 200 and response.json()['archiveId'] is None


def test_completed_history_readable_and_mutations_locked(studio):
    client, factory, _, task, material, _ = studio
    original = save_archive(studio)
    assert transition(client, task, 'complete', 2).status_code == 200
    assert send(client, task, key='blocked').status_code == 409
    assert post(client, task, '/studio/conversations', {}, 'blocked').status_code == 409
    assert post(client, task, '/studio/archive', {
        'pictureIds': [original['turns'][0]['pictures'][0]['id']], 'sku': 'A'}, 'blocked').status_code == 409
    root = ROOT + '/tasks/' + task['id'] + '/studio'
    assert client.post(root + '/files', files={'file': ('note.txt', b'text')}, headers=HEADERS).status_code == 409
    assert client.delete(root + '/materials/task:' + material['id'], headers=HEADERS).status_code == 409
    assert client.get(root + '/transcript').status_code == 200
    assert client.get(original['turns'][0]['pictures'][0]['url']).status_code == 200
    assert client.get(original['materials'][0]['url']).status_code == 200
    assert client.get(ROOT + '/archives/' + original['archiveId']).status_code == 200


def test_lifecycle_sql_failure_rolls_back_state_audit_and_request(studio, monkeypatch):
    from app.overseas.studio import service
    client, factory, _, task, _, _ = studio
    save_archive(studio)
    def fail(*args):
        raise RuntimeError('injected persistence failure')
    monkeypatch.setattr(service, 'request_record', fail)
    with pytest.raises(RuntimeError, match='injected persistence failure'):
        transition(client, task, 'complete', 2)
    with factory() as session:
        assert session.get(Task, UUID(task['id'])).status == 'studio'
        assert session.get(Task, UUID(task['id'])).version == 2
        assert session.scalar(select(TaskEvent).where(TaskEvent.kind == 'task.studio_completed')) is None
        assert session.scalar(select(TaskOutbox).where(TaskOutbox.topic == 'task.studio_completed')) is None
        assert session.scalar(select(TaskRequest).where(TaskRequest.operation == 'studio_complete')) is None
