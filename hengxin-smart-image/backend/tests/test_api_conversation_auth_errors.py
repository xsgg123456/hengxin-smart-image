"""Real domain/runner branches with synthetic CLI evidence, no production or model calls."""
import json

import pytest

from app.modules.api_image_edits import conversation_runner as runner
from app.modules.api_image_edits.conversation_errors import AUTH_ERROR, execution_error
from test_api_cli_conversation import (cli_enabled, seed_gate, submit, run, fake_executor)
from test_api_image_versions import setup_result
from test_api_image_domain import enabled_api
from files_helpers import files_env


@pytest.mark.parametrize('exit_code', [0, 1])
@pytest.mark.parametrize('message', [
    'workspace routing discovery unauthorized (401)',
    'HTTP 401 Unauthorized: sensitive-token /home/private/path',
    'refresh_token_reused secret',
])
def test_authentication_failure_uses_safe_message_and_keeps_formal_image(
        files_env, monkeypatch, message, exit_code):
    client, factory, store, _ = files_env
    _, original, path = setup_result(client, factory)
    calls = fake_executor(monkeypatch, exit_code=exit_code)
    original_execute = runner.execute
    def execute(*args):
        receipt = original_execute(*args)
        with (args[2] / 'events.jsonl').open('a') as out:
            out.write(json.dumps({'type': 'turn.failed', 'error': {'message': message}}) + '\n')
        return receipt
    monkeypatch.setattr(runner, 'execute', execute)
    run(factory, store, submit(client, path))
    view = client.get(path + '/conversation').json()
    assert len(calls) == 1
    assert view['turns'][0]['error'] == AUTH_ERROR
    assert view['turns'][0]['candidate'] is None and view['currentVersion'] == 1
    assert view['turns'][0]['baseFileId'] == original['result']['fileId']


def test_preflight_credential_error_never_dispatches(files_env, monkeypatch):
    client, factory, store, _ = files_env
    _, _, path = setup_result(client, factory)
    calls = fake_executor(monkeypatch)
    def reject(*args, **kwargs):
        raise runner.CredentialsError()
    monkeypatch.setattr(runner, 'sync_credentials', reject)
    run(factory, store, submit(client, path))
    view = client.get(path + '/conversation').json()
    assert not calls
    assert view['turns'][0]['status'] == 'failed'
    assert '请管理员恢复登录' in view['turns'][0]['error']


@pytest.mark.parametrize('reason,expected', [
    ('timeout', '超过本轮执行时限'), ('output_limit', '日志超过安全上限'),
    ('cancelled', '已停止'), (None, 'Codex 登录凭据已失效'),
])
def test_actual_stop_reason_takes_precedence(tmp_path, reason, expected):
    (tmp_path / 'stderr.log').write_text('ERROR codex_login::auth::manager: Failed to refresh token: secret')
    assert expected in execution_error(tmp_path, {'reason': reason, 'exit_code': 1})


def test_model_text_tool_output_and_invalid_events_cannot_inject_diagnostic(tmp_path):
    events = [[], None, {'type': 'turn.failed', 'error': 'wrong-shape'},
              {'type': 'item.completed', 'item': {'type': 'agent_message',
                  'text': 'workspace routing discovery unauthorized (401)'}}]
    (tmp_path / 'events.jsonl').write_text('bad json\n' + '\n'.join(json.dumps(e) for e in events))
    assert '本轮执行失败' in execution_error(tmp_path, {'exit_code': 1})
    assert '本轮执行失败' in execution_error(tmp_path / 'missing', {'exit_code': 1})


def test_real_sync_keeps_resume_bound_to_original_account(files_env, monkeypatch, cli_enabled):
    from pathlib import Path
    from app.execution.managed_credentials import sync_credentials
    from test_managed_credentials import auth, write
    client, factory, store, _ = files_env
    _, _, path = setup_result(client, factory)
    source = Path(cli_enabled.codex_auth_file)
    write(source, auth(ttl=86400))
    monkeypatch.setattr(runner, 'sync_credentials', sync_credentials)
    calls = fake_executor(monkeypatch)
    run(factory, store, submit(client, path))
    view = client.get(path + '/conversation').json()
    assert view['turns'][0]['status'] == 'waiting_user'
    home = Path(cli_enabled.codex_execution_root) / 'api-edits' / view['id'] / 'home'
    private = home / '.codex/auth.json'
    assert json.loads(private.read_bytes())['tokens']['refresh_token'] == ''
    # A model-writable private auth file cannot replace the server-owned binding.
    write(source, auth(ttl=86400, account='another-workspace'))
    write(private, auth(ttl=86400, account='another-workspace'))
    run(factory, store, submit(client, path, text='继续调整'))
    view = client.get(path + '/conversation').json()
    assert len(calls) == 1 and view['turns'][1]['status'] == 'failed'
    assert '账号或工作区已变更' in view['turns'][1]['error']
    assert view['currentVersion'] == 1
