from pathlib import Path
from uuid import UUID, uuid4
import os
import pytest
from sqlalchemy import delete, select
from app.core.config import get_settings
from app.overseas.tasks.cleanup import cleanup_once
from app.overseas.tasks.models import Task
from app.overseas.archives.models import Archive, ArchiveAsset
from app.overseas.studio.models import Picture
from app.overseas.execution.models import Job
from app.overseas.tasks import cleanup_process
from test_overseas_task_deletion import deletion, request, generated, archived
from test_overseas_studio import studio, send
from test_overseas_materials import materials
from test_overseas_tasks import overseas, ROOT


def test_historical_archive_corruption_preserves_all_source_then_recovers(deletion):
    client, factory, _, task, _, store = deletion
    rows = generated(deletion)
    archive = archived(deletion, rows[:1])
    with factory.begin() as session:
        for row in session.scalars(select(ArchiveAsset)):
            store.data.pop(row.object_key)
        session.execute(delete(ArchiveAsset))
        record = session.get(Archive, UUID(archive['id']))
        record.created_by = record.designer_id = record.skus = None
    original = store.data[rows[0]['object_key']]
    store.data[rows[0]['object_key']] = b'corrupt'
    before = dict(store.data)
    request(client, task)
    assert cleanup_once(factory, store) == 0
    assert store.data == before
    state = client.get(ROOT + '/tasks/' + task['id']).json()
    assert state['deletionStatus'] == 'delete_failed' and '归档' in state['deletionError']
    store.data[rows[0]['object_key']] = original
    request(client, task)
    assert cleanup_once(factory, store) == 1
    view = client.get(ROOT + '/archives/' + archive['id']).json()
    assert client.get(view['pictures'][0]['url']).content == original


def test_midway_storage_failure_restart_keeps_archive_and_resumes(deletion, monkeypatch):
    client, factory, _, task, _, store = deletion
    rows = generated(deletion)
    archive = archived(deletion, rows[:1])
    original = store.remove
    removed = []
    def fail_second(row):
        if removed:
            raise OSError('internal sensitive connection string')
        original(row)
        removed.append(row.object_key)
    monkeypatch.setattr(store, 'remove', fail_second)
    request(client, task)
    assert cleanup_once(factory, store) == 0 and len(removed) == 1
    status = client.get(ROOT + '/tasks/' + task['id'] + '/deletion').json()
    assert status['status'] == 'delete_failed' and 'internal' not in status['error']
    assert client.get(ROOT + '/archives/' + archive['id'] + '/download').status_code == 200
    # New session/maintenance pass replays the durable inventory, including missing objects.
    monkeypatch.setattr(store, 'remove', original)
    request(client, task)
    assert cleanup_once(factory, store) == 1
    assert client.get(ROOT + '/archives/' + archive['id'] + '/download').status_code == 200


def test_storage_delete_requires_verified_absence(deletion, monkeypatch):
    client, factory, _, task, _, store = deletion
    monkeypatch.setattr(store, 'remove', lambda _: None)
    request(client, task)
    assert cleanup_once(factory, store) == 0
    assert client.get(ROOT + '/tasks/' + task['id'] + '/deletion').json()['status'] == 'delete_failed'
    with factory() as session:
        assert session.get(Task, UUID(task['id'])) is not None


@pytest.mark.parametrize('unsafe', ['../foreign', '/absolute', 'skills/shared/SKILL.md', 'studio/../other'])
def test_storage_namespace_traversal_blocks_before_any_delete(deletion, unsafe):
    client, factory, _, task, _, store = deletion
    rows = generated(deletion, 1)
    with factory.begin() as session:
        row = session.get(Picture, UUID(rows[0]['id']))
        row.object_key = unsafe
    before = dict(store.data)
    request(client, task)
    assert cleanup_once(factory, store) == 0
    assert store.data == before


@pytest.mark.parametrize('link_type', ['hardlink', 'symlink'])
def test_workspace_links_never_delete_shared_target(deletion, link_type):
    client, factory, _, task, _, store = deletion
    turn = send(client, task).json()['turns'][0]
    from app.overseas.studio.models import Conversation
    with factory() as session:
        channel = session.scalar(select(Conversation))
        directory = Path(get_settings().codex_execution_root) / 'studio' / str(channel.id)
    directory.mkdir(parents=True)
    target = directory.parent.parent / 'shared.txt'
    target.write_text('must retain')
    try:
        (os.link if link_type == 'hardlink' else os.symlink)(target, directory / 'linked')
    except OSError as exc:
        pytest.skip(f'OS does not permit {link_type}: {exc}')
    before = dict(store.data)
    request(client, task)
    assert cleanup_once(factory, store) == 0
    assert target.read_text() == 'must retain' and store.data == before


def test_terminal_leader_exit_does_not_substitute_for_group_exit(deletion, monkeypatch):
    client, factory, _, task, _, store = deletion
    generated(deletion, 1)
    with factory.begin() as session:
        job = session.scalar(select(Job))
        job.worker_node = get_settings().worker_node_name
        job.process_id, job.process_boot, job.process_started = 123, 'boot', 'birth'
    monkeypatch.setattr(cleanup_process, 'group_alive', lambda _: True)
    request(client, task)
    assert cleanup_once(factory, store) == 0
    assert client.get(ROOT + '/tasks/' + task['id']).status_code == 200
    monkeypatch.setattr(cleanup_process, 'group_alive', lambda _: False)
    assert cleanup_once(factory, store) == 1
