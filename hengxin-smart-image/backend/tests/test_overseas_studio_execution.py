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
        assert '设计产品' in prompt
        assert '商品背景' not in prompt and '用户意见' not in prompt
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
    original = workspace.inputs_root / Path(workspace.input_paths[0]['path']).relative_to('/work/inputs')
    assert original.read_bytes() == b'name,value\nitem,42\n'
    (workspace.work / 'research.txt').write_text('previous round research')
    second = send(client, task, key='second').json()['turns'][-1]
    runner.run(factory, second['jobId'])
    assert 'resume' in commands[1][1] and 'session-123' in commands[1][1]
    assert commands[0][0].home == commands[1][0].home
    assert commands[0][0].work == commands[1][0].work
    assert commands[0][0].round_work != commands[1][0].round_work
    assert original.read_bytes() == b'name,value\nitem,42\n'
    assert (commands[1][0].work / 'research.txt').read_text() == 'previous round research'
    third = send(client, task, key='third').json()['turns'][-1]
    runner.run(factory, third['jobId'])
    assert commands[2][0].work == workspace.work
    assert original.read_bytes() == b'name,value\nitem,42\n'
    assert (commands[2][0].work / 'research.txt').read_text() == 'previous round research'
    view = client.get(ROOT + '/tasks/' + task['id'] + '/studio').json()
    assert [t['status'] for t in view['turns']] == ['succeeded'] * 3


def test_runner_collects_arbitrary_multiple_images(studio, monkeypatch, tmp_path):
    client, factory, _, task, _, _ = studio
    fake_runtime(studio, monkeypatch, tmp_path, image_count=3)
    first = send(client, task).json()['turns'][0]
    runner.run(factory, first['jobId'])
    view = client.get(ROOT + '/tasks/' + task['id'] + '/studio').json()
    assert view['turns'][0]['status'] == 'succeeded', view
    assert '/work/' in view['turns'][0]['reply']
    pictures = view['turns'][0]['pictures']
    assert len(pictures) == 3 and len({p['id'] for p in pictures}) == 3
    for picture in pictures:
        assert picture['sourcePath'].startswith('/work/output')
        assert client.get(picture['url']).status_code == 200


@pytest.mark.parametrize('reply', [
    '## 中间文件\n![预览](/work/output0.png)',
    '这是草稿，暂不交付。\n\n![预览](/work/output0.png)',
    '![预览](/work/output0.png)\n\n以上只是草稿，暂不交付。',
    '这是草稿，暂不交付。\n\n![预览](/work/final.png)',
    '以下图片仅供预览，并非最终交付。\n\n![预览](/work/output0.png)',
    '这不是正式交付。\n\n![预览](/work/output0.png)',
    'These are not final images.\n\n![Preview](/work/output0.png)',
    'These are **not** final images.\n\n![Image](/work/output0.png)',
    'These are not **final images**.\n\n![Image](/work/output0.png)',
    '![**not** final images](/work/output0.png)',
    '![Image](/work/output0.png "not final images")',
    '![n&#111;t **final images**](/work/output0.png)',
    '## Test images\nFor testing only.\n\n![Image](/work/output0.png)',
    '## Experimental images\nFor experimentation.\n\n![Image](/work/output0.png)',
    '这些是工作稿。\n\n![图片](/work/output0.png)',
])
def test_non_delivery_images_never_reach_api_but_text_survives(studio, monkeypatch, tmp_path, reply):
    client, factory, _, task, _, _ = studio
    commands = fake_runtime(studio, monkeypatch, tmp_path, image_count=1)
    original = runner.execute
    def execute(*args):
        receipt = original(*args)
        workspace = commands[-1][0]
        if '/final.png' in reply:
            (workspace.work / 'output0.png').replace(workspace.work / 'final.png')
        path = args[2] / 'events.jsonl'
        events = [json.loads(line) for line in path.read_text().splitlines()]
        events[-2]['item']['text'] = reply
        path.write_text('\n'.join(json.dumps(event) for event in events))
        return receipt
    monkeypatch.setattr(runner, 'execute', execute)
    turn = send(client, task).json()['turns'][0]
    runner.run(factory, turn['jobId'])
    root = ROOT + '/tasks/' + task['id'] + '/studio'
    result = client.get(root).json()['turns'][0]
    assert result['status'] == 'succeeded' and result['pictures'] == []
    assert result['reply'] == reply
    assert client.get(root + '/transcript').json()['items'][0]['text'] == reply


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
