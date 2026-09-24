import json
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from app.core.config import get_settings
from app.execution.material_literals import image_calls
from app.execution.material_history import read_history, history, public_text
from app.execution.material_capture import freeze_calls
from app.execution import material_backfill
from app.models import utcnow
from app.modules.tasks.models import RoundRecord, TaskRecord, ImageVersion
from app.modules.tasks.attempts import ExecutionAttempt
from app.resource_models import UserRecord
from files_helpers import files_env
from test_tasks import task_env, submit, job_for
from app.execution.fixture_runner import run_generation


def evidence(tmp_path, task_id, round_id, started, prompt='系统原文'):
    control = tmp_path / str(task_id) / 'control' / str(round_id)
    control.mkdir(parents=True)
    (control / 'request.txt').write_text(prompt, encoding='utf-8')
    logs = tmp_path / str(task_id) / 'home' / '.codex' / 'sessions'
    logs.mkdir(parents=True, exist_ok=True)
    def entry(payload, offset=1):
        return {'timestamp': (started + timedelta(seconds=offset)).isoformat(),
                'type': 'response_item', 'payload': payload}
    user = lambda text: {'type': 'message', 'role': 'user', 'content': [{'type': 'input_text', 'text': text}]}
    call = lambda text: {'type': 'function_call', 'name': 'exec', 'arguments':
        'const result = await tools.image_gen__imagegen(' + json.dumps({'prompt': text,
        'referenced_image_paths': ['/work/current/00.png', '/home/private/secret.png']}, ensure_ascii=False) + ');'}
    records = [entry(user('上一轮'), -5), entry(call('不能串轮'), -4), entry(user(prompt)),
               entry(call('完整内容' * 6000), 2), entry(call('第二次 /srv/private/file.png'), 3),
               entry(user('下一轮'), 4), entry(call('下一轮不展示'), 5)]
    path = logs / 'rollout.jsonl'
    path.write_text('\n'.join(json.dumps(r, ensure_ascii=False) for r in records), encoding='utf-8')
    return control, path


def test_history_full_multiple_calls_scoped_and_sanitized(tmp_path):
    task, round_id, start = uuid4(), uuid4(), utcnow()
    evidence(tmp_path, task, round_id, start)
    data = read_history(tmp_path, task, round_id, start, start + timedelta(seconds=10))
    assert len(data['toolCalls']) == 2
    assert data['toolCalls'][0]['prompt'] == '完整内容' * 6000
    assert data['toolCalls'][0]['images'] == ['/work/current/00.png']
    assert '/srv/' not in data['toolCalls'][1]['prompt']
    assert data['systemPrompts'][0]['text'] == '系统原文'


@pytest.mark.parametrize('code', [
    'tools.image_gen__imagegen({prompt: process.env.SECRET})',
    'tools.image_gen__imagegen({prompt: `hello ${secret}`})',
    'tools.image_gen__imagegen({prompt: "prefix" + secret})',
])
def test_dynamic_arguments_not_executed_or_partially_displayed(code):
    assert image_calls(code) == ([], True)


def test_literal_parser_quotes_comments_and_no_string_false_positive():
    code = '''// tools.image_gen__imagegen({prompt:"fake"});
const fake = "tools.image_gen__imagegen({prompt:'fake'})";
tools.image_gen__imagegen({prompt:'完整\\n文本', referenced_image_paths:['/work/a.png'],});'''
    calls, unsupported = image_calls(code)
    assert not unsupported and len(calls) == 1 and calls[0]['prompt'] == '完整\n文本'
    assert '/work/a.png' in calls[0]['referenced_image_paths']


@pytest.mark.parametrize('code', [
    'if (false) { tools.image_gen__imagegen({prompt:"未执行"}); }',
    'function later() { tools.image_gen__imagegen({prompt:"未执行"}); }',
    'const later = () => tools.image_gen__imagegen({prompt:"未执行"});',
    'false && tools.image_gen__imagegen({prompt:"未执行"});',
    'throw Error(); tools.image_gen__imagegen({prompt:"未执行"});',
])
def test_nonexecuted_branches_are_not_reported_as_actual_calls(code):
    assert image_calls(code) == ([], True)


def test_private_path_and_credentials_hidden():
    text = public_text('原图 /work/current/a.png /data/private.png C:\\Users\\secret.png Bearer abcdef api_key=secret')
    assert '/work/current/a.png' in text
    for private in ('/data/', 'C:', 'abcdef', '=secret'):
        assert private not in text


def test_permissions_and_limit_are_explicit(tmp_path, monkeypatch):
    import app.execution.material_history as module
    start, task, round_id = utcnow(), uuid4(), uuid4()
    evidence(tmp_path, task, round_id, start)
    monkeypatch.setattr(module, 'LIMIT', 1)
    data = read_history(tmp_path, task, round_id, start)
    assert not data['toolCalls'] and '限额' in data['notices'][-1]
    history.cache_clear()
    monkeypatch.setattr(module, 'read', lambda *a, **k: (_ for _ in ()).throw(PermissionError()))
    data = read_history(tmp_path, task, round_id, start)
    assert '权限不足' in data['notices'][0]


def endpoint(receipt):
    return f'/api/v1/tasks/{receipt["taskId"]}/rounds/{receipt["roundId"]}/materials'


def test_api_frozen_output_history_and_shared_auth(task_env):
    client, factory, store, identity = task_env
    receipt = submit(task_env).json()
    run_generation(job_for(factory, receipt), factory, store)
    data = client.get(endpoint(receipt)).json()
    assert data['note'] == '修改文字' and len(data['outputs']) == 1
    assert data['outputs'][0]['version'] == 1
    assert data['systemPrompts'] == [] and data['toolCalls'] == []
    assert client.get(data['outputs'][0]['picture']['url']).status_code == 200
    with factory.begin() as session:
        other = UserRecord(id=uuid4(), name='同事', role='designer', status='active', identity_source='development')
        session.add(other)
    identity[0] = other.id
    assert client.get(endpoint(receipt)).status_code == 200
    identity[0] = uuid4()
    assert client.get(endpoint(receipt)).status_code in (401, 403)


def test_deleted_and_cross_task_round_not_found(task_env):
    client = task_env[0]
    first = submit(task_env).json()
    second = submit(task_env, key='second').json()
    assert client.get(endpoint({**first, 'roundId': second['roundId']})).status_code == 404
    client.delete('/api/v1/tasks/' + first['taskId'])
    assert client.get(endpoint(first)).status_code == 404


def test_freeze_and_backfill_dry_run_idempotent(task_env, tmp_path, monkeypatch):
    client, factory, _, _ = task_env
    receipt = submit(task_env).json()
    start = utcnow()
    control, _ = evidence(tmp_path, receipt['taskId'], receipt['roundId'], start, '系统原文 /work/targets/00.png')
    from files_helpers import image_bytes
    target = tmp_path / receipt['taskId'] / 'rounds' / receipt['roundId'] / 'targets' / '00.png'
    target.parent.mkdir(parents=True)
    target.write_bytes(image_bytes())
    monkeypatch.setattr(get_settings(), 'codex_execution_root', str(tmp_path))
    with factory.begin() as session:
        row = session.get(RoundRecord, UUID(receipt['roundId']))
        attempt = ExecutionAttempt(id=uuid4(), task_id=row.task_id, round_id=row.id,
            operator_id=row.operator_id, claim_token=uuid4(), node='test', workspace=str(control),
            cli_version='test', started_at=start, finished_at=start + timedelta(seconds=10), status='finished')
        session.add(attempt)
    monkeypatch.setattr(material_backfill, 'session_factory', lambda: factory)
    material_backfill.main(['--round-id', receipt['roundId']])
    with factory() as session:
        assert 'materials' not in session.get(RoundRecord, UUID(receipt['roundId'])).execution_config
    material_backfill.main(['--round-id', receipt['roundId'], '--write'])
    target.unlink()
    assert freeze_calls(factory, attempt.id)
    data = client.get(endpoint(receipt)).json()
    assert len(data['toolCalls']) == 2 and len(data['systemPrompts']) == 1
    with factory() as session:
        frozen = session.get(RoundRecord, UUID(receipt['roundId'])).execution_config['materials']
        assert frozen['captured'] and len(frozen['toolCalls']) == 2
        assert frozen['historicalInputs'][0]['verified']
    monkeypatch.setattr(material_backfill, 'freeze_calls', lambda *args: False)
    with pytest.raises(SystemExit) as error:
        material_backfill.main(['--round-id', receipt['roundId'], '--write'])
    assert error.value.code == 1


def test_capture_failure_never_escapes(monkeypatch):
    from app.execution.material_capture import freeze_prompt
    def broken():
        raise RuntimeError('database unavailable')
    assert not freeze_calls(broken, uuid4())
    assert not freeze_prompt(None, uuid4(), {}, 'prompt')


def test_capture_throttled_to_30_seconds(monkeypatch):
    import app.execution.material_capture as module
    now, calls = [0], []
    monkeypatch.setattr(module.time, 'monotonic', lambda: now[0])
    monkeypatch.setattr(module, 'freeze_calls', lambda *args: calls.append(args))
    ticker = module.CaptureTicker('factory', 'attempt')
    for second in (0, 1, 10, 29, 30, 31, 59, 60):
        now[0] = second
        ticker.tick()
    assert len(calls) == 2


def test_historical_inputs_require_prompt_and_matching_bytes(task_env, tmp_path):
    from app.execution.material_bindings import historical_inputs
    from files_helpers import image_bytes
    receipt = submit(task_env).json()
    work = tmp_path / receipt['taskId'] / 'rounds' / receipt['roundId'] / 'targets'
    work.mkdir(parents=True)
    path = work / '00.png'
    path.write_bytes(image_bytes())
    with task_env[1]() as session:
        task = session.get(TaskRecord, UUID(receipt['taskId']))
        row = session.get(RoundRecord, UUID(receipt['roundId']))
        assert not historical_inputs(session, task, row, tmp_path, [])[0]['verified']
        prompts = [{'text': '本轮底图 /work/targets/00.png'}]
        assert historical_inputs(session, task, row, tmp_path, prompts)[0]['verified']
        path.write_bytes(b'wrong')
        assert not historical_inputs(session, task, row, tmp_path, prompts)[0]['verified']


def test_first_round_outputs_stay_bound_after_revision(task_env):
    from test_revisions import revise
    client, factory, store, _ = task_env
    first = submit(task_env).json()
    run_generation(job_for(factory, first), factory, store)
    original = client.get(endpoint(first)).json()['outputs']
    revision = revise(task_env, first).json()
    run_generation(job_for(factory, revision), factory, store)
    assert client.get(endpoint(first)).json()['outputs'] == original
    assert client.get(endpoint(revision)).json()['outputs'][0]['version'] == 2
