"""Native CLI arg0 shims must not prevent deletion of a stopped task."""
import os
import shutil
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4
from zipfile import ZipFile

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.overseas.execution.models import Job
from app.overseas.studio.models import Conversation
from app.overseas.tasks import cleanup_files
from app.overseas.tasks.cleanup import cleanup_once
from app.overseas.tasks.models import Task
from test_overseas_task_deletion import deletion, request, generated, archived
from test_overseas_studio import studio
from test_overseas_materials import materials
from test_overseas_tasks import overseas, ROOT

pytestmark = pytest.mark.skipif(os.name != 'posix', reason='Production CLI links require native Linux')
SHIMS = ('apply_patch', 'applypatch', 'codex-execve-wrapper', 'codex-linux-sandbox')


def shims(private):
    directory = private / 'home/.codex/tmp/arg0/codex-arg0s37Lkj'
    directory.mkdir(parents=True)
    for name in SHIMS:
        (directory / name).symlink_to('/opt/codex')
    return directory


def archive_contents(client, identity):
    response = client.get(ROOT + '/archives/' + identity + '/download')
    assert response.status_code == 200
    with ZipFile(BytesIO(response.content)) as bundle:
        return [(name, bundle.read(name)) for name in bundle.namelist()]


@pytest.mark.parametrize('workflow', ['legacy', 'studio'])
def test_cli_shims_allow_real_cleanup_and_archive_survives(deletion, workflow):
    client, factory, _, task, _, store = deletion
    root = Path(get_settings().codex_execution_root)
    archive = original = None
    if workflow == 'legacy':
        with factory.begin() as session:
            session.get(Task, UUID(task['id'])).workflow = 'legacy'
            job = Job(task_id=UUID(task['id']), kind='analysis', dedupe_key='stopped',
                payload={}, status='cancelled', execution_count=1, process_exited=True)
            session.add(job)
            session.flush()
            private = root / str(job.id)
    else:
        rows = generated(deletion, 1)
        archive = archived(deletion, rows)
        original = archive_contents(client, archive['id'])
        with factory() as session:
            channel = session.scalar(select(Conversation).where(Conversation.task_id == UUID(task['id'])))
            private = root / 'studio' / str(channel.id)
    shims(private)
    shared = root / 'shared-skill.txt'
    shared.write_bytes(b'must remain')
    assert request(client, task).status_code == 200
    assert cleanup_once(factory, store) == 1
    assert not private.exists() and shared.read_bytes() == b'must remain'
    assert client.get(ROOT + '/tasks/' + task['id']).status_code == 404
    assert client.get(ROOT + '/tasks/' + task['id'] + '/deletion').json()['status'] == 'deleted'
    if archive:
        assert archive_contents(client, archive['id']) == original


@pytest.mark.parametrize('invalid', ['target', 'name', 'directory', 'location', 'parent', 'hardlink'])
def test_cli_lookalikes_block_before_any_object_erasure(deletion, invalid):
    client, factory, _, task, _, store = deletion
    generated(deletion, 1)
    with factory() as session:
        channel = session.scalar(select(Conversation).where(Conversation.task_id == UUID(task['id'])))
        private = Path(get_settings().codex_execution_root) / 'studio' / str(channel.id)
    directory = shims(private)
    shared = private.parent.parent / 'shared.txt'
    shared.write_bytes(b'must remain')
    path = directory / 'apply_patch'
    path.unlink()
    if invalid == 'target':
        path.symlink_to(shared)
    elif invalid == 'name':
        (directory / 'unknown-tool').symlink_to('/opt/codex')
    elif invalid == 'directory':
        directory.rename(directory.with_name('unknown-prefix'))
    elif invalid == 'location':
        (private / 'apply_patch').symlink_to('/opt/codex')
    elif invalid == 'parent':
        outside = private.parent.parent / 'foreign'
        directory.rename(outside)
        directory.symlink_to(outside, target_is_directory=True)
    else:
        os.link(shared, path)
    before = dict(store.data)
    request(client, task)
    assert cleanup_once(factory, store) == 0
    assert store.data == before and private.exists()
    assert shared.read_bytes() == b'must remain'
    assert client.get(ROOT + '/tasks/' + task['id'] + '/deletion').json()['status'] == 'delete_failed'
    if invalid == 'target':
        path.unlink()
        path.symlink_to('/opt/codex')
        request(client, task)
        assert cleanup_once(factory, store) == 1
        assert shared.read_bytes() == b'must remain'


def test_cli_links_require_symlink_resistant_erasure(tmp_path, monkeypatch):
    root = tmp_path / 'execution'
    identity = str(uuid4())
    shims(root / identity)
    monkeypatch.setattr(cleanup_files, 'get_settings', lambda: type('Settings', (), {'codex_execution_root': str(root)})())
    monkeypatch.setattr(shutil.rmtree, 'avoids_symlink_attacks', False)
    with pytest.raises(ValueError, match='Linked workspace'):
        cleanup_files.validate_directories(dict(root=str(root), directories=[identity]))
