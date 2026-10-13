"""Real HTTP + isolated SQL/object bytes, without executing or deleting production data."""
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from uuid import UUID
from zipfile import ZipFile
import pytest
from sqlalchemy import select, func
from app.core.config import get_settings
from app.overseas.tasks.cleanup import cleanup_once
from app.overseas.tasks.models import Task, TaskDeletion
from app.overseas.archives.models import Archive, ArchiveAsset
from app.overseas.execution.models import Job
from app.overseas.execution import claims
from app.overseas.studio.models import Conversation, Turn, Picture
from test_overseas_tasks import overseas, create, payload, ROOT, HEADERS
from test_overseas_materials import materials
from test_overseas_studio import studio, send, finish, output
from test_overseas_assignment import change_roles
from test_overseas_plans import post


@pytest.fixture
def deletion(studio, tmp_path):
    get_settings().codex_execution_root = str(tmp_path / 'execution')
    return studio


def request(client, task, **overrides):
    current = client.get(ROOT + '/tasks/' + task['id']).json()
    return client.request('DELETE', ROOT + '/tasks/' + task['id'],
        json=dict(version=current.get('version', 1), confirmationName=task['name'], **overrides), headers=HEADERS)


def generated(fixture, count=2):
    client, factory, _, task, _, store = fixture
    turn = send(client, task).json()['turns'][0]
    rows = [output(store) for _ in range(count)]
    for row in rows:
        key = row['object_key']
        row['object_key'] = 'studio/pictures/' + row['id']
        store.data[row['object_key']] = store.data.pop(key)
    finish(factory, turn, rows)
    return rows


def archived(fixture, rows):
    client, _, _, task, _, _ = fixture
    response = post(client, task, '/studio/archive',
        dict(pictureIds=[row['id'] for row in rows], sku='A'), 'archive')
    assert response.status_code == 200, response.text
    return client.get(ROOT + '/archives').json()['items'][0]


@pytest.mark.parametrize('role', ['operator', 'operator_manager', 'designer', 'design_manager'])
def test_non_admin_cannot_delete_own_or_assigned_task(deletion, role):
    client, factory, actor, task, _, _ = deletion
    with factory.begin() as session:
        session.get(Task, UUID(task['id'])).designer_id = actor
    change_roles(factory, actor, (role,))
    assert 'task.delete' not in client.get(ROOT + '/tasks/' + task['id']).json()['capabilities']
    assert request(client, task).status_code == 403
    with factory() as session:
        assert session.get(TaskDeletion, UUID(task['id'])) is None


@pytest.mark.parametrize('count', [0, 1, 2])
def test_delete_cleans_task_and_exact_archived_versions_survive(deletion, count):
    client, factory, actor, task, _, store = deletion
    rows = generated(deletion)
    archive = archived(deletion, rows[:count]) if count else None
    before = [sha256(store.data[row['object_key']]).hexdigest() for row in rows[:count]]
    other = create(client, payload(UUID(task['designer']['id'])), 'other').json()
    shared = Path(get_settings().codex_execution_root) / 'shared-skill'
    shared.mkdir(parents=True)
    (shared / 'SKILL.md').write_text('shared')
    with factory() as session:
        channel = session.scalar(select(Conversation).where(Conversation.task_id == UUID(task['id'])))
        private = shared.parent / 'studio' / str(channel.id)
    (private / 'home' / '.codex' / 'sessions').mkdir(parents=True)
    (private / 'home' / '.codex' / 'sessions' / 'session.jsonl').write_text('private dialogue')
    response = request(client, task)
    assert response.status_code == 200 and response.json()['status'] == 'deleting'
    state = client.get(ROOT + '/tasks/' + task['id']).json()
    assert state['status'] == 'deleting' and state['capabilities'] == ['task.read', 'task.delete']
    assert send(client, task, key='late').status_code == 409
    assert post(client, task, '/studio/archive', dict(pictureIds=[rows[0]['id']], sku='A'), 'late').status_code == 409
    assert cleanup_once(factory, store) == 1
    assert not private.exists() and (shared / 'SKILL.md').read_text() == 'shared'
    assert client.get(ROOT + '/tasks/' + task['id']).status_code == 404
    assert client.get(ROOT + '/tasks/' + other['id']).status_code == 200
    assert client.get(ROOT + '/tasks/' + task['id'] + '/deletion').json()['status'] == 'deleted'
    assert request(client, task).json()['status'] == 'deleted'
    with factory() as session:
        assert session.get(Task, UUID(task['id'])) is None
        for model in (Turn, Picture, Job, Conversation):
            assert session.scalar(select(func.count()).select_from(model).where(model.task_id == UUID(task['id']))) == 0
        receipt = session.get(TaskDeletion, UUID(task['id']))
        assert receipt.manifest == {} and receipt.error is None
    assert all(row['object_key'] not in store.data for row in rows)
    if archive:
        view = client.get(ROOT + '/archives/' + archive['id']).json()
        assert view['sourceDeleted'] and view['taskId'] is None and view['pictureCount'] == count
        assert view['skus'] == [{'code': 'A'}, {'code': 'B'}]
        assert [sha256(client.get(row['url']).content).hexdigest() for row in view['pictures']] == before
        zipped = client.get(ROOT + '/archives/' + archive['id'] + '/download')
        with ZipFile(BytesIO(zipped.content)) as bundle:
            assert [sha256(bundle.read(name)).hexdigest() for name in bundle.namelist()] == before
        assert client.get(ROOT + '/archives?sku=A&search=手机').json()['total'] == 1
        assert client.get(ROOT + '/archives?sku=code').json()['total'] == 0
        change_roles(factory, actor, ('designer',))
        assert client.get(ROOT + '/archives').json()['total'] == 0
        assert client.get(view['pictures'][0]['url']).status_code == 403
        assert client.get(ROOT + '/archives/' + archive['id'] + '/download').status_code == 403


def test_confirmation_version_browser_and_duplicate_guards(deletion):
    client, factory, _, task, _, store = deletion
    url = ROOT + '/tasks/' + task['id']
    for body, status in [(dict(version=2, confirmationName='wrong'), 422),
                         (dict(version=1, confirmationName=task['name']), 409)]:
        assert client.request('DELETE', url, json=body, headers=HEADERS).status_code == status
    assert client.request('DELETE', url, json=dict(version=2, confirmationName=task['name'])).status_code == 403
    assert request(client, task).json()['status'] == 'deleting'
    assert request(client, task).json()['status'] == 'deleting'
    assert cleanup_once(factory, store) == 1
    assert cleanup_once(factory, store) == 0


def test_running_unknown_and_late_publication_remain_fenced(deletion):
    client, factory, _, task, _, store = deletion
    turn = send(client, task).json()['turns'][0]
    job_id = UUID(turn['jobId'])
    token = claims.claim(factory, job_id)
    assert request(client, task).json()['status'] == 'deleting'
    assert cleanup_once(factory, store) == 0
    assert store.data and client.get(ROOT + '/tasks/' + task['id']).status_code == 200
    assert not claims.finish(factory, job_id, token, 'succeeded', {'reply': 'late'})
    with factory.begin() as session:
        job = session.get(Job, job_id)
        job.status = 'uncertain'
    assert cleanup_once(factory, store) == 0
    with factory.begin() as session:
        job = claims.locked_job(session, job_id)
        job.process_exited = True
        claims.end(session, job, 'cancelled')
    assert cleanup_once(factory, store) == 1
    assert not claims.finish(factory, job_id, token, 'succeeded', {'reply': 'late'})
