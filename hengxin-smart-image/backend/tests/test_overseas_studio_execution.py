"""Exercise the real runner/collector with a fake process boundary, never CLI."""
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID
import pytest
from sqlalchemy import select
from app.core.config import get_settings
from app.overseas.execution import runner, protocols, claims
from app.overseas.execution.models import Job
from app.overseas.studio import execution
from app.overseas.studio.models import Conversation, Turn
from test_overseas_studio import studio, send
from test_overseas_materials import materials
from test_overseas_tasks import overseas, ROOT


def fake_runtime(studio, monkeypatch, tmp_path, image_count=0, crash=False):
    client, factory, _, task, _, store = studio
    settings = get_settings()
    settings.enable_codex_executor = True
    settings.codex_execution_root = str(tmp_path / 'execution')
    auth = tmp_path / 'auth.json'
    auth.write_text('{}')
    settings.codex_auth_file = str(auth)
    monkeypatch.setitem(protocols._handlers, 'studio', execution.HANDLER)
    monkeypatch.setattr(execution, 'get_store', lambda: store)
    monkeypatch.setattr(runner, 'resources_available', lambda _: True)
    monkeypatch.setattr(runner.subprocess, 'run', lambda *a, **kw:
                        SimpleNamespace(returncode=0, stdout='codex-cli ' + settings.codex_version))
    commands = []
    def sandbox(workspace, binary, args, bwrap):
        commands.append((workspace, args))
        return ['fake-cli']
    monkeypatch.setattr(runner, 'sandbox_command', sandbox)
    def execute(command, prompt, control, timeout, monitor, started):
        assert '用户意见' in prompt
        workspace, args = commands[-1]
        started(123, 'boot', 'birth')
        if crash:
            raise RuntimeError('process state unknown')
        events = [dict(type='thread.started', thread_id='session-123'),
                  dict(type='turn.started')]
        (control / 'events.jsonl').write_text('\n'.join(json.dumps(e) for e in events))
        assert not monitor()
        sessions = workspace.home / '.codex/sessions'
        sessions.mkdir(parents=True, exist_ok=True)
        (sessions / 'rollout-session-123.jsonl').write_text('{}')
        reply = '请确认方向'
        if image_count:
            from PIL import Image
            reply = ''
            for number in range(image_count):
                name = f'output{number}.png'
                Image.new('RGB', (24, 24), 'blue').save(workspace.work / name)
                reply += f'![设计](/work/{name})\n'
        events += [dict(type='item.completed', item=dict(type='agent_message', text=reply)),
                   dict(type='turn.completed', usage=dict(input_tokens=2, output_tokens=3))]
        (control / 'events.jsonl').write_text('\n'.join(json.dumps(e) for e in events))
        return dict(exit_code=0)
    monkeypatch.setattr(runner, 'execute', execute)
    return commands


def test_runner_text_then_resume_and_original_inputs(studio, monkeypatch, tmp_path):
    client, factory, _, task, material, _ = studio
    commands = fake_runtime(studio, monkeypatch, tmp_path)
    first = send(client, task, attachmentIds=['task:' + material['id']]).json()['turns'][0]
    runner.run(factory, first['jobId'])
    with factory() as session:
        assert session.get(Job, UUID(first['jobId'])).status == 'succeeded'
        assert session.scalar(select(Conversation)).session_id == 'session-123'
    workspace = commands[0][0]
    assert (workspace.work / 'inputs/1.csv').read_bytes() == b'name,value\nitem,42\n'
    second = send(client, task, key='second').json()['turns'][-1]
    runner.run(factory, second['jobId'])
    assert 'resume' in commands[1][1] and 'session-123' in commands[1][1]
    assert commands[0][0].home == commands[1][0].home
    assert commands[0][0].work != commands[1][0].work
    view = client.get(ROOT + '/tasks/' + task['id'] + '/studio').json()
    assert [t['status'] for t in view['turns']] == ['succeeded', 'succeeded']


def test_runner_collects_arbitrary_multiple_images(studio, monkeypatch, tmp_path):
    client, factory, _, task, _, _ = studio
    fake_runtime(studio, monkeypatch, tmp_path, image_count=3)
    first = send(client, task).json()['turns'][0]
    runner.run(factory, first['jobId'])
    view = client.get(ROOT + '/tasks/' + task['id'] + '/studio').json()
    assert view['turns'][0]['status'] == 'succeeded', view
    assert '/work/' not in view['turns'][0]['reply']
    pictures = view['turns'][0]['pictures']
    assert len(pictures) == 3 and len({p['id'] for p in pictures}) == 3
    for picture in pictures:
        assert client.get(picture['url']).status_code == 200


def test_crash_stays_uncertain_no_replacement_or_duplicate_spawn(studio, monkeypatch, tmp_path):
    client, factory, _, task, _, _ = studio
    commands = fake_runtime(studio, monkeypatch, tmp_path, crash=True)
    first = send(client, task).json()['turns'][0]
    runner.run(factory, first['jobId'])
    runner.run(factory, first['jobId'])
    assert len(commands) == 1
    with factory() as session:
        assert session.get(Job, UUID(first['jobId'])).status == 'uncertain'
    assert send(client, task, key='again').status_code == 409


def test_missing_original_session_does_not_start_replacement(studio, monkeypatch, tmp_path):
    client, factory, _, task, _, _ = studio
    commands = fake_runtime(studio, monkeypatch, tmp_path)
    first = send(client, task).json()['turns'][0]
    runner.run(factory, first['jobId'])
    (commands[0][0].home / '.codex/sessions/rollout-session-123.jsonl').unlink()
    second = send(client, task, key='next').json()['turns'][-1]
    runner.run(factory, second['jobId'])
    assert len(commands) == 1
    with factory() as session:
        assert session.get(Job, UUID(second['jobId'])).status == 'failed'
