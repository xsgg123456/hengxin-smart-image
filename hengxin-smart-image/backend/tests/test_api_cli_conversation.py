"""Isolated API/worker tests: no network, credentials or real CLI execution."""
import json
from contextlib import nullcontext
from datetime import timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4
import pytest
from sqlalchemy import select
from app.core.config import get_settings
from app.models import Job, utcnow
from app.modules.api_image_edits import conversation, conversation_runner as runner
from app.modules.api_image_edits.conversation_models import Conversation, ConversationTurn
from app.modules.api_image_edits.conversation_runtime import claim, sweep
from app.modules.api_image_edits.conversation_router import read_events
from app.modules.api_image_edits.models import ApiItem
from app.resource_models import UserRecord
from app.modules.tasks.models import ExecutionGate
from files_helpers import files_env, image_bytes
from test_api_image_domain import ROOT, enabled_api, upload
from test_api_image_versions import setup_result, post


@pytest.fixture(autouse=True)
def seed_gate(files_env):
    with files_env[1].begin() as session:
        session.add(ExecutionGate(id=1))


@pytest.fixture(autouse=True)
def cli_enabled(monkeypatch, tmp_path):
    auth = tmp_path / 'auth.json'
    auth.write_text('{}')
    settings = SimpleNamespace(**get_settings().model_dump())
    settings.enable_codex_executor = True
    settings.codex_execution_root = str(tmp_path / 'execution')
    settings.codex_auth_file = str(auth)
    settings.codex_binary = 'fake-codex'
    monkeypatch.setattr(conversation, 'get_settings', lambda: settings)
    monkeypatch.setattr(runner, 'get_settings', lambda: settings)
    monkeypatch.setattr(runner, 'heartbeat', lambda *args: nullcontext())
    monkeypatch.setattr(runner.subprocess, 'run', lambda *args, **kwargs:
                        SimpleNamespace(returncode=0, stdout=f'codex-cli {settings.codex_version}'))
    monkeypatch.setattr(runner, 'sandbox_command', lambda workspace, binary, args, bwrap: args)
    return settings


def submit(client, path, **kwargs):
    response = post(client, path + '/conversation/turns', {'text': '调整屏幕', 'baseVersion': 1, **kwargs})
    assert response.status_code == 202, response.text
    return response.json()['turns'][-1]


def fake_executor(monkeypatch, text='请确认颜色', image=False, reason=None, exit_code=0):
    calls = []
    def execute(args, prompt, control, timeout, monitor, started):
        calls.append((args, prompt))
        sid = 'session-single-image'
        sessions = control.parents[1] / 'home' / '.codex' / 'sessions'
        sessions.mkdir(exist_ok=True)
        (sessions / (sid + '.jsonl')).write_text('{}')
        final = text
        if image:
            work = control.parents[1] / 'rounds' / control.name
            (work / 'output.png').write_bytes(image_bytes())
            final = '![成品](/work/output.png)'
        events = [{'type': 'thread.started', 'thread_id': sid},
                  {'type': 'item.completed', 'item': {'type': 'reasoning', 'text': '秘密推理'}},
                  {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': final}},
                  {'type': 'turn.completed'}]
        (control / 'events.jsonl').write_text('\n'.join(json.dumps(e) for e in events) + '\n')
        return {'exit_code': exit_code, 'reason': reason}
    monkeypatch.setattr(runner, 'execute', execute)
    return calls


def run(factory, store, turn):
    with factory() as session:
        job_id = session.get(ConversationTurn, UUID(turn['id'])).job_id
    runner.run_turn(job_id, factory, store)
    return job_id


def test_submit_freezes_three_four_inputs_idempotency_and_api_exclusion(files_env):
    client, factory, _, _ = files_env
    task_id, item, path = setup_result(client, factory)
    annotation = upload(client)
    body = {'text': '1.保持原样\n整体：更明亮', 'baseVersion': 1,
            'annotationFileId': annotation['fileId'], 'prompt': '不可覆盖固定模板'}
    url = path + '/conversation/turns'
    result = post(client, url, body, 'same')
    assert result.status_code == 202, result.text
    assert len(post(client, url, body, 'same').json()['turns']) == 1
    assert post(client, url, {**body, 'text': '不同'}, 'same').status_code == 409
    assert post(client, url, body).status_code == 409
    assert post(client, path + '/revise', {'text': '文字', 'baseVersion': 1}).status_code == 409
    assert client.delete(f'{ROOT}/tasks/{task_id}').status_code == 409
    assert client.delete(ROOT + '/files/' + annotation['fileId']).status_code == 409
    with factory() as session:
        turn = session.scalar(select(ConversationTurn))
        assert len(turn.snapshot['fileIds']) == 4
        assert turn.snapshot['fileIds'][0] == item['result']['fileId']
        assert body['text'] in turn.prompt and '不可覆盖固定模板' not in turn.prompt
        assert turn.snapshot['policyVersion'] == 'api-image-edit-v2'


def test_text_then_exact_resume_candidate_explicit_adoption(files_env, monkeypatch):
    client, factory, store, identity = files_env
    task_id, original, path = setup_result(client, factory)
    calls = fake_executor(monkeypatch)
    first = submit(client, path)
    run(factory, store, first)
    view = client.get(path + '/conversation').json()
    assert view['turns'][0]['status'] == 'waiting_user'
    assert view['turns'][0]['messages'] == ['Codex：请确认颜色']
    assert view['currentVersion'] == 1
    calls = fake_executor(monkeypatch, image=True)
    second = submit(client, path, text='用蓝色')
    run(factory, store, second)
    assert 'resume' in calls[0][0] and 'session-single-image' in calls[0][0]
    view = client.get(path + '/conversation').json()
    assert view['turns'][1]['status'] == 'candidate' and view['currentVersion'] == 1
    candidate = view['turns'][1]['candidate']
    assert (candidate['width'], candidate['height']) == (8, 6)
    assert client.get(f'{ROOT}/tasks/{task_id}').json()['items'][0]['result'] == original['result']
    endpoint = path + '/conversation/turns/' + second['id'] + '/adopt'
    assert post(client, endpoint, {'expectedVersion': 2}).status_code == 409
    assert post(client, endpoint, {'expectedVersion': 1}, 'adopt').json()['currentVersion'] == 2
    assert post(client, endpoint, {'expectedVersion': 1}, 'adopt').json()['currentVersion'] == 2
    all_events = read_events(factory, identity[0], UUID(task_id), UUID(original['id']), 0)
    assert [e['id'] for e in all_events] == list(range(1, len(all_events) + 1))
    assert read_events(factory, identity[0], UUID(task_id), UUID(original['id']), 2) == all_events[2:]
    assert '秘密推理' not in str(all_events)


def test_candidate_base_stop_and_permission(files_env, monkeypatch):
    client, factory, store, identity = files_env
    task_id, item, path = setup_result(client, factory)
    fake_executor(monkeypatch, image=True)
    first = submit(client, path)
    run(factory, store, first)
    candidate = client.get(path + '/conversation').json()['turns'][0]['candidateFileId']
    second = submit(client, path, baseVersion=None, baseTurnId=first['id'])
    assert second['baseFileId'] == candidate and second['annotation'] is None
    stopped = post(client, path + '/conversation/turns/' + second['id'] + '/stop').json()
    assert stopped['turns'][1]['status'] == 'cancelled'
    with factory.begin() as session:
        session.get(UserRecord, identity[0]).status = 'disabled'
    with pytest.raises(Exception) as error:
        read_events(factory, identity[0], UUID(task_id), UUID(item['id']), 0)
    assert error.value.status_code == 403


@pytest.mark.parametrize('reason,code', [('timeout', -15), (None, 1)])
def test_timeout_and_failed_process_never_publish(files_env, monkeypatch, reason, code):
    client, factory, store, _ = files_env
    _, _, path = setup_result(client, factory)
    fake_executor(monkeypatch, image=True, reason=reason, exit_code=code)
    turn = submit(client, path)
    run(factory, store, turn)
    view = client.get(path + '/conversation').json()
    assert view['turns'][0]['status'] == 'failed'
    assert view['turns'][0]['candidate'] is None and view['currentVersion'] == 1


def test_expired_execution_never_replays(files_env):
    client, factory, _, _ = files_env
    _, _, path = setup_result(client, factory)
    turn = submit(client, path)
    with factory() as session:
        job_id = session.get(ConversationTurn, UUID(turn['id'])).job_id
    assert claim(factory, job_id)
    with factory.begin() as session:
        session.get(Job, job_id).lease_until = utcnow() - timedelta(seconds=1)
    sweep(factory)
    assert claim(factory, job_id) is None
    assert client.get(path + '/conversation').json()['turns'][0]['status'] == 'uncertain'


def test_missing_session_refuses_new_thread_and_invalid_delivery_fails(files_env, monkeypatch, cli_enabled):
    client, factory, store, _ = files_env
    _, _, path = setup_result(client, factory)
    calls = fake_executor(monkeypatch, text='![成品](/work/missing.png)')
    first = submit(client, path)
    run(factory, store, first)
    assert client.get(path + '/conversation').json()['turns'][0]['status'] == 'failed'
    for file in __import__('pathlib').Path(cli_enabled.codex_execution_root).rglob('session-single-image.jsonl'):
        file.unlink()
    second = submit(client, path)
    run(factory, store, second)
    assert len(calls) == 1
    assert client.get(path + '/conversation').json()['turns'][1]['status'] == 'failed'


def test_cancellation_during_process_fences_late_result(files_env, monkeypatch):
    client, factory, store, _ = files_env
    _, _, path = setup_result(client, factory)
    fake_executor(monkeypatch, image=True)
    original = runner.execute
    turn = submit(client, path)
    def execute(*args):
        result = original(*args)
        assert post(client, path + '/conversation/turns/' + turn['id'] + '/stop').status_code == 200
        return result
    monkeypatch.setattr(runner, 'execute', execute)
    run(factory, store, turn)
    result = client.get(path + '/conversation').json()
    assert result['turns'][0]['status'] == 'cancelled'
    assert result['turns'][0]['candidate'] is None and result['currentVersion'] == 1


def test_uncertain_stop_requires_worker_process_proof(files_env, monkeypatch, cli_enabled):
    from app.modules.api_image_edits import conversation_stop
    client, factory, store, _ = files_env
    _, _, path = setup_result(client, factory)
    turn = submit(client, path)
    with factory() as session:
        job_id = session.get(ConversationTurn, UUID(turn['id'])).job_id
    assert claim(factory, job_id)
    with factory.begin() as session:
        current = session.get(ConversationTurn, UUID(turn['id']))
        current.process_identity = {'pid': 1234, 'boot': 'boot', 'birth': 'birth',
                                    'node': get_settings().worker_node_name}
        session.get(Job, job_id).lease_until = None
    sweep(factory)
    post(client, path + '/conversation/turns/' + turn['id'] + '/stop')
    monkeypatch.setattr(conversation_stop, 'same_process', lambda *args: False)
    cli_enabled.enable_codex_executor = False
    runner.run_turn(job_id, factory, store)
    assert client.get(path + '/conversation').json()['turns'][0]['status'] == 'cancelled'


def test_cli_and_api_modes_share_item_mutex_in_both_directions(files_env):
    client, factory, _, _ = files_env
    _, _, path = setup_result(client, factory)
    assert post(client, path + '/revise', {'text': '文字修改', 'baseVersion': 1}).status_code == 202
    result = post(client, path + '/conversation/turns', {'text': '图片修改', 'baseVersion': 1})
    assert result.status_code == 409


def test_cli_capacity_counts_existing_batch_jobs(files_env):
    client, factory, _, _ = files_env
    _, _, path = setup_result(client, factory)
    turn = submit(client, path)
    with factory.begin() as session:
        session.add(Job(id=uuid4(), kind='generation', value='batch', payload_hash='x' * 64,
                        idempotency_key='batch', status='running'))
        job_id = session.get(ConversationTurn, UUID(turn['id'])).job_id
    assert claim(factory, job_id) is None
    assert client.get(path + '/conversation').json()['turns'][0]['status'] == 'queued'


def test_candidate_normalized_to_original_dimensions(files_env, monkeypatch):
    from PIL import Image
    from io import BytesIO
    from types import SimpleNamespace
    from app.modules.files.validation import validate_image
    client, factory, store, _ = files_env
    _, _, path = setup_result(client, factory)
    turn = submit(client, path)
    with factory() as session:
        job_id = session.get(ConversationTurn, UUID(turn['id'])).job_id
    token = claim(factory, job_id)
    buffer = BytesIO()
    Image.new('RGB', (32, 32)).save(buffer, format='PNG')
    buffer.seek(0)
    image = validate_image(SimpleNamespace(file=buffer, filename='candidate.png', content_type='image/png'))
    runner.complete(factory, store, job_id, token, image=image)
    result = client.get(path + '/conversation').json()
    candidate = result['turns'][0]['candidate']
    assert (candidate['width'], candidate['height']) == (8, 6)
    assert result['currentVersion'] == 1
