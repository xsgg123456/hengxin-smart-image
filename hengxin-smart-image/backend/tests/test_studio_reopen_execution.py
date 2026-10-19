"""Complete/reopen retain the actual runner's resume protocol and persistent files."""
from hashlib import sha256
from uuid import UUID
import pytest
from sqlalchemy import select
from app.overseas.execution import runner
from app.overseas.execution.models import Job
from app.overseas.studio.models import Conversation
from test_overseas_studio import studio, send
from test_overseas_studio_execution import fake_runtime
from test_overseas_materials import materials
from test_overseas_tasks import overseas
from test_overseas_plans import post
from test_studio_reopen import transition, view


def file_snapshot(path):
    return {str(file.relative_to(path)): sha256(file.read_bytes()).hexdigest()
            for file in path.rglob('*') if file.is_file()}


def run_archived(studio, monkeypatch, tmp_path):
    client, factory, _, task, material, _ = studio
    commands = fake_runtime(studio, monkeypatch, tmp_path, image_count=1)
    first = send(client, task, attachmentIds=['task:' + material['id']]).json()['turns'][0]
    runner.run(factory, first['jobId'])
    data = view(client, task)
    assert data['turns'][0]['status'] == 'succeeded', data
    picture = data['turns'][0]['pictures'][0]
    assert post(client, task, '/studio/archive', {'pictureIds': [picture['id']], 'sku': 'A'}, 'archive').status_code == 200
    return commands, view(client, task)


def test_reopen_keeps_files_and_sends_on_exact_original_session(studio, monkeypatch, tmp_path):
    client, factory, _, task, _, store = studio
    commands, before = run_archived(studio, monkeypatch, tmp_path)
    workspace = commands[0][0]
    research = workspace.work / 'research.txt'
    research.write_text('保留研究与草稿', encoding='utf-8')
    root = workspace.home.parent
    files, objects = file_snapshot(root), dict(store.data)
    assert transition(client, task, 'complete', before['taskVersion']).status_code == 200
    reopened = transition(client, task, 'reopen', before['taskVersion'] + 1).json()
    assert not reopened['completed'] and reopened['reopened']
    for field in ('conversationId', 'turns', 'materials', 'archiveId'):
        assert reopened[field] == before[field]
    assert len(commands) == 1 and file_snapshot(root) == files and store.data == objects
    second = send(client, task, key='after-reopen').json()['turns'][-1]
    assert second['conversationId'] == before['conversationId']
    runner.run(factory, second['jobId'])
    assert len(commands) == 2
    assert 'resume' in commands[1][1] and 'session-123' in commands[1][1]
    assert commands[1][0].home == workspace.home and commands[1][0].work == workspace.work
    assert research.read_text(encoding='utf-8') == '保留研究与草稿'
    assert all(store.data[key] == value for key, value in objects.items())
    with factory() as session:
        assert session.get(Job, UUID(second['jobId'])).status == 'succeeded'
        assert session.get(Conversation, UUID(before['conversationId'])).session_id == 'session-123'


@pytest.mark.parametrize('missing', ['identity', 'session_file'])
def test_reopen_never_silently_replaces_missing_original_session(studio, monkeypatch, tmp_path, missing):
    client, factory, _, task, _, _ = studio
    commands, before = run_archived(studio, monkeypatch, tmp_path)
    transition(client, task, 'complete', before['taskVersion'])
    assert transition(client, task, 'reopen', before['taskVersion'] + 1).status_code == 200
    if missing == 'identity':
        with factory.begin() as session:
            session.scalar(select(Conversation)).session_id = None
    else:
        (commands[0][0].home / '.codex/sessions/rollout-session-123.jsonl').unlink()
    second = send(client, task, key='after-reopen').json()['turns'][-1]
    runner.run(factory, second['jobId'])
    assert len(commands) == 1
    assert view(client, task)['conversationId'] == before['conversationId']
    with factory() as session:
        assert session.get(Job, UUID(second['jobId'])).status == 'failed'
