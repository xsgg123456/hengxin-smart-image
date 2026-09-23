"""CLI boundary stub; real admission, materials, collection and persistence remain active."""
import json

from app.execution import codex_runner as runner
from files_helpers import image_bytes
from test_codex_runner import frozen_request
from test_tasks import body


def create_set(env, mode='wallpaper'):
    return frozen_request(env, body(env, mode))


def scripted_cli(monkeypatch, env, receipt, outcomes=('no_delivery', 'success'), hook=None):
    calls = []
    def execute(args, prompt, control, timeout, stop, start):
        index = len(calls)
        calls.append({'args': args, 'prompt': prompt, 'control': control, 'timeout': timeout})
        outcome = outcomes[index]
        root = control.parent.parent
        work = root / 'rounds' / receipt['roundId']
        home = root / 'home/.codex'
        session_id = 'intervention-session'
        start(1001 + index, 'boot', str(101 + index))
        if outcome == 'crash_before_events':
            raise OSError('worker interrupted after spawn')
        native = home / 'generated_images' / session_id
        native.mkdir(parents=True, exist_ok=True)
        logs = home / 'sessions'
        logs.mkdir(exist_ok=True)
        if outcome != 'missing_session':
            (logs / f'rollout-{session_id}.jsonl').write_text('{}')
        candidate = native / 'kept-first.png'
        if index == 0:
            candidate.write_bytes(image_bytes())
            (work / 'progress.json').write_text('{"completed": [1]}')
        else:
            assert candidate.read_bytes() == image_bytes()
            assert json.loads((work / 'progress.json').read_text()) == {'completed': [1]}
        (work / 'second.png').write_bytes(image_bytes())
        events = [{'type': 'thread.started', 'thread_id': session_id}]
        if outcome in ('success', 'crash_after_delivery'):
            text = f'![图片1](/home/runner/.codex/generated_images/{session_id}/kept-first.png)\n![图片2](/work/second.png)'
        elif outcome == 'incomplete':
            text = '![图片1](/work/second.png)'
        elif outcome == 'invalid_file':
            text = '![图片1](/work/missing.png)\n![图片2](/work/second.png)'
        else:
            text = '结果尚未达到要求，已保存进度。'
        if outcome in ('auth', 'quota', 'limited', 'network', 'chinese_quota'):
            errors = {'auth': '401 Unauthorized', 'quota': 'insufficient_quota',
                      'limited': '429 rate limit', 'network': 'stream disconnected',
                      'chinese_quota': '额度已用尽'}
            events.append({'type': 'error', 'message': errors[outcome]})
        events += [{'type': 'item.completed', 'item': {'type': 'agent_message', 'text': text}},
                   {'type': 'turn.completed', 'usage': {'input_tokens': 7, 'output_tokens': 2}}]
        if outcome == 'session_change':
            events += [{'type': 'thread.started', 'thread_id': 'unexpected-session'},
                       {'type': 'turn.failed', 'error': {'message': 'stream disconnected'}}]
        if outcome == 'wrong_session' and index:
            events[0]['thread_id'] = 'unexpected-session'
        (control / 'request.txt').write_text(prompt, encoding='utf-8')
        (control / 'events.jsonl').write_text('\n'.join(json.dumps(e) for e in events), encoding='utf-8')
        (control / 'stderr.log').write_text('insufficient credits' if outcome == 'stderr_quota' else '')
        if hook:
            hook(index, stop)
        if outcome == 'crash_after_delivery':
            raise OSError('worker interrupted after CLI completed')
        result = {'exit_code': -15 if outcome == 'timeout' else 1 if outcome == 'nonzero' else 0,
                  'reason': 'timeout' if outcome == 'timeout' else None}
        (control / 'exit.json').write_text(json.dumps(result))
        return result
    monkeypatch.setattr(runner, 'execute', execute)
    return calls
