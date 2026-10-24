"""HTTP receipt tests: isolated DB, real disk bytes, fake external storage only."""
from io import BytesIO
from types import SimpleNamespace
from uuid import UUID
from zipfile import ZipFile
import os
import pytest
from PIL import Image
from sqlalchemy import select, func

from app.core.config import get_settings
from app.overseas.execution.models import Job
from app.overseas.studio import delivery_context, delivery_snapshot, recovery_files, recovery_listing
from app.overseas.studio.models import Turn, ConversationDeletion, Picture, OutputFile
from app.overseas.studio.output_files import validated
from app.overseas.tasks.models import Task, TaskDeletion, ExecutionObject
from test_overseas_assignment import change_roles
from test_overseas_materials import materials
from test_overseas_studio import studio, send, finish
from test_overseas_tasks import overseas, ROOT, HEADERS
from studio_sessions_helpers import channel


def png(color='blue'):
    output = BytesIO()
    Image.new('RGB', (24, 32), color).save(output, format='PNG')
    return output.getvalue()


@pytest.fixture
def missed(studio, tmp_path, monkeypatch):
    client, factory, actor, task, _, store = studio
    from app.overseas.studio import recovery_transport
    from studio_receipt_regression_helpers import native_request_bridge
    monkeypatch.setattr(recovery_transport, 'request', native_request_bridge(factory, store))
    first = send(client, task).json()['turns'][0]
    finish(factory, first)
    monkeypatch.setattr(get_settings(), 'codex_execution_root', str(tmp_path / 'execution'))
    with factory.begin() as session:
        turn = session.get(Turn, UUID(first['id']))
        cid = turn.conversation_id
        turn.dispatched, turn.event_session_id = True, 'thread-1'
        session.get(Task, turn.task_id).designer_id = actor
    change_roles(factory, actor, ('designer',))
    root = tmp_path / 'execution' / 'studio' / str(cid)
    work = root / 'persistent' / 'work'
    work.mkdir(parents=True)
    return SimpleNamespace(client=client, factory=factory, actor=actor, task=task, turn=first,
        store=store, root=root, work=work, cid=cid,
        url=ROOT + '/tasks/' + task['id'] + '/studio/conversations/' + str(cid))


def listed(case):
    response = case.client.get(case.url + '/recoverable-files')
    assert response.status_code == 200, response.text
    return response.json()


def take(case, items=None):
    items = listed(case)['items'] if items is None else items
    return case.client.post(case.url + '/recover-files', headers=HEADERS,
        json={'files': [{k: item[k] for k in ('id', 'version')} for item in items]})


def count(case, model):
    with case.factory() as session:
        return session.scalar(select(func.count()).select_from(model))


def test_designer_recovers_mixed_originals_without_model_or_admin_gate(missed):
    (missed.work / 'picture.png').write_bytes(png())
    archive = BytesIO()
    with ZipFile(archive, 'w') as zipped:
        zipped.writestr('notes.txt', 'hello')
    (missed.work / 'bundle.zip').write_bytes(archive.getvalue())
    (missed.work / 'empty.txt').touch()
    (missed.work / 'broken.png').write_bytes(b'invalid image bytes')
    items = listed(missed)
    assert not items['busy'] and len(items['items']) == 4
    assert next(i for i in items['items'] if i['name'] == 'empty.txt')['sizeBytes'] == 0
    response = take(missed, items['items'])
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['errors'] == [] and len(result['saved']) == 4
    assert count(missed, Picture) == 1 and count(missed, OutputFile) == 3
    assert count(missed, ExecutionObject) == 4
    assert take(missed).json()['saved'] == result['saved']
    assert count(missed, ExecutionObject) == 4
    with missed.factory() as session:
        job = session.get(Job, UUID(missed.turn['jobId']))
        assert job.execution_count == 1 and job.status == 'succeeded'
        for model in (Picture, OutputFile):
            for row in session.scalars(select(model)):
                assert missed.store.data[row.object_key] == (missed.work / row.name).read_bytes()


def test_same_name_new_bytes_are_a_new_version_and_stale_selection_fails(missed):
    path = missed.work / 'design.png'
    path.write_bytes(png())
    old = listed(missed)['items']
    first = take(missed, old).json()['saved'][0]
    path.write_bytes(png('red'))
    response = take(missed, old).json()
    assert not response['saved'] and '变化' in response['errors'][0]['message']
    second = take(missed).json()['saved'][0]
    assert first['id'] != second['id'] and count(missed, Picture) == 2


@pytest.mark.parametrize('status', ['failed', 'cancelled'])
def test_stopped_failed_turn_needs_no_success_receipt(missed, status):
    (missed.work / 'notes.txt').write_bytes(b'partial useful output')
    with missed.factory.begin() as session:
        job = session.get(Job, UUID(missed.turn['jobId']))
        job.status, job.cancel_requested, job.result = status, True, None
    assert take(missed).json()['errors'] == []
    assert count(missed, OutputFile) == 1


def test_only_linked_native_image_directory_and_unprotected_work_are_listed(missed):
    for relative in ('home/.codex/generated_images/thread-1/result.png',
                     'home/.codex/generated_images/unrelated/secret.png', 'home/.codex/auth.json',
                     'control/secret.txt', 'persistent/work/inputs/private.png',
                     'persistent/work/skills/SKILL.md', 'persistent/work/input.json'):
        path = missed.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(png())
    data = listed(missed)['items']
    assert len(data) == 1 and data[0]['source'] == 'native'
    assert data[0]['path'] == '/home/runner/.codex/generated_images/thread-1/result.png'
    assert take(missed, data).json()['saved'][0]['kind'] == 'picture'


def test_old_snapshot_wins_over_overwritten_work_and_preserves_original_identity(missed):
    old = png()
    (missed.work / 'design.png').write_bytes(png('red'))
    with missed.factory() as session:
        job = session.get(Job, UUID(missed.turn['jobId']))
        identity = delivery_context.identity(job)
    control = missed.root / 'control' / missed.turn['id'] / 'delivery'
    delivery_snapshot.begin(control, identity, 'done', 'thread-1', ['/work/design.png'])
    manifest = delivery_snapshot.capture(control, '/work/design.png', validated(old, 'design.png'))
    item = next(i for i in listed(missed)['items'] if i['source'] == 'snapshot')
    response = take(missed, [item]).json()
    assert response['errors'] == []
    assert response['saved'][0]['id'] == manifest['items'][0]['pictureId']
    with missed.factory() as session:
        picture = session.get(Picture, UUID(response['saved'][0]['id']))
        assert missed.store.data[picture.object_key] == old
    assert take(missed, [item]).json()['saved'] == response['saved']


def test_partial_failure_keeps_successes_and_can_retry(missed, monkeypatch):
    (missed.work / 'good.txt').write_bytes(b'good')
    (missed.work / 'bad.txt').write_bytes(b'bad')
    original = missed.store.put
    def put(row, data):
        if data == b'bad':
            raise RuntimeError('private storage diagnostic')
        original(row, data)
    monkeypatch.setattr(missed.store, 'put', put)
    result = take(missed).json()
    assert len(result['saved']) == len(result['errors']) == 1
    assert result['errors'][0]['name'] == 'bad.txt'
    assert 'private' not in result['errors'][0]['message']
    assert count(missed, OutputFile) == 1 and count(missed, ExecutionObject) == 2
    monkeypatch.setattr(missed.store, 'put', original)
    assert len(take(missed).json()['saved']) == 2
    assert count(missed, OutputFile) == 2 and count(missed, ExecutionObject) == 2


@pytest.mark.parametrize('state', ['completed', 'task-delete', 'channel-delete', 'running', 'unconfirmed'])
def test_readonly_deletion_and_current_process_block_receipt(missed, state):
    (missed.work / 'result.txt').write_bytes(b'output')
    choices = listed(missed)['items']
    with missed.factory.begin() as session:
        task = session.get(Task, UUID(missed.task['id']))
        job = session.get(Job, UUID(missed.turn['jobId']))
        if state == 'completed': task.status = 'completed'
        elif state == 'task-delete': session.add(TaskDeletion(task_id=task.id, actor_id=missed.actor))
        elif state == 'channel-delete':
            session.add(ConversationDeletion(conversation_id=missed.cid, task_id=task.id, actor_id=missed.actor))
        elif state == 'running': job.status = 'running'
        else: job.process_exited = False
    if state in ('running', 'unconfirmed'):
        assert listed(missed) == {'items': [], 'busy': True}
    assert take(missed, choices).status_code == 409
    assert count(missed, OutputFile) == count(missed, ExecutionObject) == 0


def test_other_conversation_running_does_not_block_and_ids_cannot_cross(missed):
    (missed.work / 'result.txt').write_bytes(b'output')
    first = listed(missed)['items']
    other = channel(missed.client, missed.task, 'other')
    send(missed.client, missed.task, key='other-run', conversationId=other)
    assert not listed(missed)['busy']
    assert take(missed, first).json()['errors'] == []
    response = missed.client.post(missed.url.replace(str(missed.cid), other) + '/recover-files',
        headers=HEADERS, json={'files': [{k: first[0][k] for k in ('id', 'version')}]})
    assert response.status_code == 409
    with missed.factory.begin() as session:
        turn = session.scalar(select(Turn).where(Turn.conversation_id == UUID(other)))
        job = session.get(Job, turn.job_id)
        job.status, job.process_exited = 'cancelled', True
    response = missed.client.post(missed.url.replace(str(missed.cid), other) + '/recover-files',
        headers=HEADERS, json={'files': [{k: first[0][k] for k in ('id', 'version')}]})
    assert response.json()['saved'] == [] and len(response.json()['errors']) == 1


def test_link_and_oversized_files_are_not_candidates(missed, tmp_path):
    path = missed.work / 'linked.txt'
    path.write_bytes(b'secret')
    os.link(path, tmp_path / 'outside.txt')
    with (missed.work / 'huge.bin').open('wb') as stream:
        stream.truncate(recovery_listing.MAX_BYTES + 1)
    assert listed(missed)['items'] == []


def test_browser_protection_request_bounds_and_no_client_paths(missed):
    url = missed.url + '/recover-files'
    assert missed.client.post(url, json={'files': []}).status_code == 403
    for files in ([], [{'id': 'x', 'version': 'x'}] * 101,
                  [{'id': 'x', 'version': 'x', 'path': '/etc/passwd'}]):
        assert missed.client.post(url, headers=HEADERS, json={'files': files}).status_code == 422


def test_deletion_between_ledger_and_publication_stops_late_save(missed, monkeypatch):
    (missed.work / 'result.txt').write_bytes(b'output')
    original, calls = recovery_files.guard, []
    def changed(session, *args, **kwargs):
        calls.append(True)
        if len(calls) == 4:
            with missed.factory.begin() as other:
                other.add(TaskDeletion(task_id=UUID(missed.task['id']), actor_id=missed.actor))
        return original(session, *args, **kwargs)
    choices = listed(missed)['items']
    monkeypatch.setattr(recovery_files, 'guard', changed)
    result = take(missed, choices).json()
    assert not result['saved'] and len(result['errors']) == 1
    assert count(missed, OutputFile) == 0 and count(missed, ExecutionObject) == 1


@pytest.mark.parametrize('data', [b'', b'zip or unknown original bytes'])
def test_ordinary_file_snapshot_is_recovered_even_after_original_disappears(missed, data):
    with missed.factory() as session:
        job = session.get(Job, UUID(missed.turn['jobId']))
        identity = delivery_context.identity(job)
    control = missed.root / 'control' / missed.turn['id'] / 'delivery'
    delivery_snapshot.begin(control, identity, 'done', 'thread-1', ['/work/bundle.zip'])
    delivery_snapshot.capture(control, '/work/bundle.zip', validated(data, 'bundle.zip'))
    result = take(missed).json()
    assert result['errors'] == [] and result['saved'][0]['kind'] == 'file'
    with missed.factory() as session:
        row = session.get(OutputFile, UUID(result['saved'][0]['id']))
        assert missed.store.data[row.object_key] == data


def test_legacy_round_work_and_replaced_file_during_read(missed, monkeypatch):
    old_work = missed.root / 'rounds' / missed.turn['id']
    old_work.mkdir(parents=True)
    path = old_work / 'legacy.txt'
    path.write_bytes(b'old data')
    choices = listed(missed)['items']
    assert choices[0]['path'] == '/work/legacy.txt'
    from contextlib import contextmanager
    original = recovery_listing.fs.reader
    @contextmanager
    def replacing(source):
        with original(source) as stream:
            yield stream
        path.write_bytes(b'replaced data')
    monkeypatch.setattr(recovery_listing.fs, 'reader', replacing)
    result = take(missed, choices).json()
    assert not result['saved'] and '变化' in result['errors'][0]['message']
    assert count(missed, ExecutionObject) == 0


@pytest.mark.parametrize('change', ['permission', 'file-removed'])
def test_selection_is_reauthorized_and_removed_files_fail_individually(missed, change):
    path = missed.work / 'output.txt'
    path.write_bytes(b'useful output')
    choices = listed(missed)['items']
    if change == 'permission':
        change_roles(missed.factory, missed.actor, ('operator',))
        assert take(missed, choices).status_code == 403
    else:
        path.unlink()
        response = take(missed, choices).json()
        assert response['saved'] == [] and len(response['errors']) == 1
    assert count(missed, OutputFile) == count(missed, ExecutionObject) == 0


def test_private_os_error_with_chinese_path_is_not_exposed(missed, monkeypatch):
    (missed.work / 'output.txt').write_bytes(b'output')
    choices = listed(missed)['items']
    def fail(*_args):
        raise OSError('private/root/secret/中文.png')
    monkeypatch.setattr(recovery_listing, 'read', fail)
    result = take(missed, choices).json()
    assert len(result['errors']) == 1 and 'private' not in result['errors'][0]['message']
