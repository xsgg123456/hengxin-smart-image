import base64
import json
from unittest.mock import Mock

import pytest
from pydantic import SecretStr, ValidationError
from urllib3.exceptions import NewConnectionError, ReadTimeoutError, SSLError

from app.modules.api_image_edits.config import ApiImageSettings, PARAMETERS
from app.modules.api_image_edits.relay import RelayClient, RelayError, retry_after_seconds
from app.modules.api_image_edits.downloads import approved_target, download_result, ResultDownloadError


def config(**kwargs):
    return ApiImageSettings(_env_file=None, api_key=SecretStr('test-only-key'), **kwargs)


def response(status=200, payload=None, headers=None):
    value = Mock(status=status, headers=headers or {}, connection=None)
    value.read1.side_effect = [json.dumps(payload or {'data': [{'url': 'https://cdn3.dmiapi.com/test.png'}]}).encode(), b'']
    return value


def generate(client):
    return client.generate(b'first', 'image/png', b'second', 'image/jpeg', 'same prompt', PARAMETERS)


def test_fixed_payload_two_images_one_request_no_transport_retry():
    pool = Mock(); pool.request.return_value = response()
    result = generate(RelayClient(config(), pool))
    assert result.result_url == 'https://cdn3.dmiapi.com/test.png'
    kwargs = pool.request.call_args.kwargs
    body = json.loads(kwargs['body'])
    assert {key: body[key] for key in PARAMETERS} == PARAMETERS
    assert body['prompt'] == 'same prompt'
    assert [base64.b64decode(item['image_url'].split(',')[1]) for item in body['images']] == [b'first', b'second']
    assert kwargs['retries'] is False and kwargs['redirect'] is False
    assert pool.request.call_count == 1
    assert 'test-only-key' not in repr(result)


def test_text_only_revision_sends_only_current_result_without_extra_prompt():
    pool = Mock(); pool.request.return_value = response()
    RelayClient(config(), pool).generate(b'current-result', 'image/png', None, None, '修正边缘', PARAMETERS)
    body = json.loads(pool.request.call_args.kwargs['body'])
    assert body['prompt'] == '修正边缘'
    assert len(body['images']) == 1
    assert base64.b64decode(body['images'][0]['image_url'].split(',')[1]) == b'current-result'


@pytest.mark.parametrize(('status', 'kind'), [(429, 'retryable'), (503, 'retryable'),
    (401, 'channel'), (402, 'channel'), (403, 'channel'), (400, 'permanent'), (408, 'uncertain')])
def test_http_error_categories_are_sanitized(status, kind):
    pool = Mock(); pool.request.return_value = response(status, headers={'Retry-After': '7'})
    with pytest.raises(RelayError) as exc:
        generate(RelayClient(config(), pool))
    assert exc.value.kind == kind
    assert 'test-only-key' not in str(exc.value)
    if kind == 'retryable': assert exc.value.retry_after == 7
    assert pool.request.call_count == 1


@pytest.mark.parametrize(('status', 'code'), [(429, 'insufficient_quota'),
    (429, 'credit_balance_exhausted'), (400, 'model_not_found'), (503, 'invalid_model')])
def test_explicit_channel_error_overrides_generic_http_status(status, code):
    pool = Mock(); pool.request.return_value = response(status, {'error': {
        'code': code, 'message': 'private upstream details'}})
    with pytest.raises(RelayError) as error:
        generate(RelayClient(config(), pool))
    assert error.value.kind == 'channel'
    assert 'private' not in str(error.value)


def test_oversized_error_body_keeps_status_classification():
    pool = Mock(); reply = response(429)
    reply.read1.side_effect = [b'x' * 17000]
    pool.request.return_value = reply
    with pytest.raises(RelayError) as error:
        generate(RelayClient(config(), pool))
    assert error.value.kind == 'retryable'


@pytest.mark.parametrize(('error', 'kind'), [
    (NewConnectionError(None, 'secret transport detail'), 'retryable'),
    (ReadTimeoutError(None, '/secret-url', 'secret detail'), 'uncertain')])
def test_connect_and_post_send_uncertainty_are_distinct(error, kind):
    pool = Mock(); pool.request.side_effect = error
    with pytest.raises(RelayError) as exc: generate(RelayClient(config(), pool))
    assert exc.value.kind == kind and 'secret' not in str(exc.value)


def test_tls_error_reading_success_response_is_uncertain_not_replayable():
    pool = Mock(); reply = response()
    reply.read1.side_effect = SSLError('private post-send TLS failure')
    pool.request.return_value = reply
    with pytest.raises(RelayError) as error:
        generate(RelayClient(config(), pool))
    assert error.value.kind == 'uncertain'
    assert pool.request.call_count == 1
    assert 'private' not in str(error.value)


def test_inline_result_and_invalid_result_dont_silently_regenerate():
    pool = Mock(); pool.request.return_value = response(payload={'data': [{'b64_json': base64.b64encode(b'png').decode()}]})
    assert generate(RelayClient(config(), pool)).image_bytes == b'png'
    for payload in ({'data': []}, {'data': [1]}, {'data': [{'b64_json': '!invalid!'}]}, {'task_id': 'async'}):
        pool.request.return_value = response(payload=payload)
        with pytest.raises(RelayError, match='核实') as exc: generate(RelayClient(config(), pool))
        assert exc.value.kind == 'uncertain'


def test_deadline_and_response_size_are_bounded():
    client = RelayClient(config(max_download_bytes=1024), Mock())
    reply = response(); reply.read1.side_effect = [b'x' * 70000, b'']
    with pytest.raises(RelayError) as exc: client._parse(reply)
    assert exc.value.kind == 'uncertain'
    assert retry_after_seconds('invalid') is None
    with pytest.raises(ValidationError): config(base_url='http://localhost')
    with pytest.raises(ValidationError): config(allowed_result_hosts=['*.example.com'])
    with pytest.raises(ValidationError): config(lease_seconds=60)


@pytest.mark.parametrize('url', ['http://cdn3.dmiapi.com/x', 'https://evil.example/x',
    'https://cdn3.dmiapi.com.evil.example/x', 'https://user:pass@cdn3.dmiapi.com/x',
    'https://cdn3.dmiapi.com:444/x', 'https://cdn3.dmiapi.com/x#fragment'])
def test_result_download_rejects_unapproved_targets(url):
    with pytest.raises(ResultDownloadError): approved_target(url, ['cdn3.dmiapi.com'])


def test_download_pins_public_ip_and_sends_no_credentials(monkeypatch):
    monkeypatch.setattr('socket.getaddrinfo', lambda *args, **kwargs: [(2, 1, 6, '', ('1.1.1.1', 443))])
    reply = Mock(status=200, headers={'Content-Length': '3'}, connection=None)
    reply.read1.side_effect = [b'png', b'']
    pool = Mock(); pool.urlopen.return_value = reply
    factory = Mock(return_value=pool)
    assert download_result('https://cdn3.dmiapi.com/result.png?token=private', config(), factory) == b'png'
    assert factory.call_args.args[0] == '1.1.1.1'
    assert factory.call_args.kwargs['server_hostname'] == 'cdn3.dmiapi.com'
    headers = pool.urlopen.call_args.kwargs['headers']
    assert headers == {'Host': 'cdn3.dmiapi.com', 'Accept': 'image/*'}
    assert pool.urlopen.call_args.kwargs['redirect'] is False
    reply.status = 302
    with pytest.raises(ResultDownloadError): download_result('https://cdn3.dmiapi.com/x', config(), factory)
    monkeypatch.setattr('socket.getaddrinfo', lambda *args, **kwargs: [(2, 1, 6, '', ('127.0.0.1', 443))])
    with pytest.raises(ResultDownloadError): approved_target('https://cdn3.dmiapi.com/x', ['cdn3.dmiapi.com'])
