import json

import pytest

from app.execution.credential_errors import authentication_failed, execution_error_code


@pytest.mark.parametrize('message', [
    'Workspace routing discovery unauthorized (401)', '401 Unauthorized',
    'refresh_token_reused', 'refresh_token_expired', 'refresh_token_invalidated',
    'authentication token is invalid',
])
def test_only_fixed_auth_classification_leaves_logs(tmp_path, message):
    path = tmp_path / 'events.jsonl'
    path.write_text(json.dumps({'type': 'turn.failed', 'error': {'message': message}}))
    assert authentication_failed(tmp_path)
    assert execution_error_code(tmp_path, {'exit_code': 1}) == 'authentication_failed'
    assert execution_error_code(tmp_path, {'reason': 'timeout'}) == 'timeout'
    assert execution_error_code(tmp_path, {'reason': 'output_limit'}) == 'output_limit'
    assert execution_error_code(tmp_path, {'reason': 'cancelled'}) == 'cancelled'


def test_unrelated_user_content_and_malformed_events_are_not_auth_errors(tmp_path):
    (tmp_path / 'events.jsonl').write_text('\n'.join([
        '[]', 'null', '{malformed', json.dumps({'type': 'item.completed', 'item': {
            'type': 'agent_message', 'text': 'refresh_token_reused'}}),
    ]))
    assert not authentication_failed(tmp_path)
    assert execution_error_code(tmp_path, {'exit_code': 1}) == 'execution_failed'
    (tmp_path / 'stderr.log').write_text('codex_login::auth: Failed to refresh token: secret')
    assert execution_error_code(tmp_path, {'exit_code': 1}) == 'authentication_failed'
