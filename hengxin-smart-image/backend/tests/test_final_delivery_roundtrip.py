"""Exercise HTTP admission, repaired output publication and same-session revisions."""
import json
from io import BytesIO

from PIL import Image

from app.execution import codex_runner as runner
from files_helpers import files_env  # noqa: F401
from test_codex_runner import real_env, frozen_request  # noqa: F401
from test_tasks import body, job_for


def png(number):
    buffer = BytesIO()
    Image.new('RGB', (800, 800), (number, 100, 200)).save(buffer, 'PNG')
    return buffer.getvalue()


def four_image_request(env):
    data = body(env, 'wallpaper')
    template = env[0].post('/api/v1/templates', json=dict(name='四张图模板', mode='wallpaper',
        images=data['sources'] * 4, skillVersionId=data['skillVersionId'], active=True, notes='测试')).json()
    data.update(templateId=template['id'], templateVersion=template['version'])
    return frozen_request(env, data)


def deliver(monkeypatch, receipt, count, offset):
    expected = [png(offset + i) for i in range(count)]
    def execute(argv, prompt, control, timeout, stop, start):
        assert '--model' in argv and 'high' in argv[argv.index('-c') + 1]
        assert 'manifest.json' not in prompt and '结果槽' not in prompt
        start(123, 'test', '1')
        work = control.parents[1] / 'rounds' / receipt['roundId']
        output = work / 'repaired'
        output.mkdir()
        native = control.parents[1] / 'home/.codex/generated_images/test-session'
        native.mkdir(parents=True, exist_ok=True)
        # More candidates than outputs, with no native byte/provenance match.
        for i in range(6):
            (native / f'exec-{offset}-{i}.png').write_bytes(png(i))
        sessions = native.parents[1] / 'sessions'
        sessions.mkdir(exist_ok=True)
        (sessions / 'test-session.jsonl').write_text('{}\n')
        links = []
        for i, data in enumerate(expected, 1):
            (output / f'final ({i}).png').write_bytes(data)
            links.append(f'![主图{i}](/work/repaired/final ({i}).png)')
        # An obsolete/misleading Skill manifest must not override explicit final delivery.
        (work / 'manifest.json').write_text('{"outputs":[{"slot":0,"error":"old error"}]}')
        events = [
            {'type': 'thread.started', 'thread_id': 'test-session'},
            {'type': 'error', 'message': 'Reconnecting... 2/5 (stream disconnected before completion: websocket closed by server before response.completed)'},
            {'type': 'item.completed', 'item': {'type': 'agent_message',
                'text': '候选：![candidate](/work/missing.png)'}},
            {'type': 'item.completed', 'item': {'type': 'command_execution', 'exit_code': 0}},
            {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': '\n'.join(links)}},
            {'type': 'turn.completed', 'usage': {'input_tokens': 1}},
        ]
        (control / 'events.jsonl').write_text('\n'.join(json.dumps(e) for e in events))
        return {'exit_code': 0, 'reason': None}
    monkeypatch.setattr(runner, 'execute', execute)
    return expected


def images(env, receipt):
    detail = env[0].get('/api/v1/tasks/' + receipt['taskId']).json()
    assert detail['task']['state'] == '待查看', detail
    return [env[0].get(item['url']).content for item in detail['task']['images']]


def test_four_repaired_outputs_and_single_then_full_revision(real_env, monkeypatch):
    created = four_image_request(real_env)
    first = deliver(monkeypatch, created, 4, 50)
    runner.run_generation(job_for(real_env[1], created), real_env[1], real_env[2])
    assert images(real_env, created) == first
    task_id = created['taskId']
    for target, count, offset in [(2, 1, 100), (None, 4, 150)]:
        response = real_env[0].post('/api/v1/tasks/' + task_id + '/rounds',
            json={'taskId': task_id, 'target': target, 'note': '换壁纸'},
            headers={'Idempotency-Key': f'revise-{offset}'})
        assert response.status_code == 202, response.text
        revision = response.json()
        new = deliver(monkeypatch, revision, count, offset)
        runner.run_generation(job_for(real_env[1], revision), real_env[1], real_env[2])
        if target is None:
            first = new
        else:
            first[target] = new[0]
        assert images(real_env, created) == first
