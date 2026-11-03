from io import BytesIO
import logging
from types import SimpleNamespace
import httpx
import pytest
from fastapi import HTTPException
from app.overseas.drafts import source, transfer
from app.overseas.drafts.http_logging import PrivateTransportFilter


@pytest.fixture
def public_dns(monkeypatch):
    monkeypatch.setattr(transfer.socket, 'getaddrinfo',
        lambda *args, **kwargs: [(2, 1, 6, '', ('104.18.1.1', 443))])


@pytest.mark.parametrize('url', [
    'http://design.qhhengxin.top/api/files/1/download?token=secret',
    'https://127.0.0.1/api/files/1/download?token=secret',
    'https://evil.test/api/files/1/download?token=secret',
    'https://design.qhhengxin.top.evil.test/api/files/1/download?token=secret',
    'https://design.qhhengxin.top:444/api/files/1/download?token=secret',
    'https://user:password@design.qhhengxin.top/api/files/1/download?token=secret',
    'https://design.qhhengxin.top/api/files/%2e%2e%2fadmin/download?token=secret',
    'https://design.qhhengxin.top/api/files/1/download',
    'https://design.qhhengxin.top/api/admin?token=secret',
])
def test_download_address_boundary(public_dns, url):
    with pytest.raises(transfer.TransferError):
        transfer.validate_url(url, initial=True)


def test_download_rejects_private_dns(monkeypatch):
    monkeypatch.setattr(transfer.socket, 'getaddrinfo', lambda *args, **kwargs: [(2, 1, 6, '', ('127.0.0.1', 443))])
    with pytest.raises(transfer.TransferError):
        transfer.validate_url(source.ORIGIN + '/api/files/1/download?token=secret', initial=True)


def test_stream_redirect_and_size_limits(public_dns, monkeypatch):
    def route(request):
        assert 'authorization' not in request.headers
        if request.url.host == 'design.qhhengxin.top':
            return httpx.Response(302, headers={'location': 'https://bucket.r2.dev/file?X-Amz-Signature=private'})
        return httpx.Response(200, content=b'abc')
    with httpx.Client(transport=httpx.MockTransport(route), follow_redirects=False) as client:
        file = BytesIO()
        result = transfer.download(client, source.ORIGIN + '/api/files/1/download?token=secret', file, 3, lambda _: None)
        assert result[0] == 3 and file.getvalue() == b'abc'
        monkeypatch.setattr(transfer, 'MAX_UPLOAD_BYTES', 2)
        with pytest.raises(transfer.TransferError, match='500 MB'):
            transfer.download(client, source.ORIGIN + '/api/files/1/download?token=secret', BytesIO(), 3, lambda _: None)


def test_redirect_off_allowlist_rejected(public_dns):
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(302,
        headers={'location': 'https://evil.test/private'}))) as client:
        with pytest.raises(transfer.TransferError):
            transfer.download(client, source.ORIGIN + '/api/files/1/download?token=secret', BytesIO(), 3, lambda _: None)


def test_source_fixed_endpoint_and_key_not_returned(monkeypatch):
    client_class = httpx.Client
    monkeypatch.setenv('OVERSEAS_DESIGN_API_KEY', 'private-test-key')
    def route(request):
        assert str(request.url).startswith(source.ORIGIN + '/api/open/sku?sku=')
        assert request.url.params['sku'] == 'A/恶意?'
        assert request.headers['authorization'] == 'Bearer private-test-key'
        return httpx.Response(200, json={'list': [], 'count': 0})
    monkeypatch.setattr(source.httpx, 'Client', lambda **kwargs: client_class(transport=httpx.MockTransport(route), **kwargs))
    assert source.fetch('A/恶意?')['list'] == []


@pytest.mark.parametrize('status', [302, 401, 403, 500])
def test_upstream_errors_are_generic(monkeypatch, status):
    client_class = httpx.Client
    monkeypatch.setenv('OVERSEAS_DESIGN_API_KEY', 'private-test-key')
    monkeypatch.setattr(source.httpx, 'Client', lambda **kwargs: client_class(transport=httpx.MockTransport(
        lambda _: httpx.Response(status, text='private credentials')), **kwargs))
    with pytest.raises(HTTPException) as result:
        source.fetch('A')
    assert result.value.status_code == 502 and 'private' not in result.value.detail


def test_missing_key_and_transport_logs_are_safe(monkeypatch):
    monkeypatch.delenv('OVERSEAS_DESIGN_API_KEY', raising=False)
    with pytest.raises(HTTPException) as result:
        source.fetch('A')
    assert result.value.status_code == 503
    for message in ('GET https://design.qhhengxin.top/api/files/1/download?token=secret',
                    "headers=[(b'Authorization', b'Bearer secret')]",
                    'location=https://bucket.r2.dev/file?X-Amz-Signature=secret'):
        entry = logging.LogRecord('httpx', logging.DEBUG, '', 0, message, (), None)
        assert not PrivateTransportFilter().filter(entry)


def test_fresh_signature_loaded_on_each_transfer(public_dns, monkeypatch):
    calls, urls = [], []
    metadata = {'list': [{'id': 'req', 'files': [{'id': 'file', 'filename': 'file.PPTX',
        'size': 3, 'downloadUrl': '/api/files/file/download?token=fresh'}]}]}
    monkeypatch.setattr(source, 'fetch', lambda sku: calls.append(sku) or metadata)
    def download(client, url, file, size, progress):
        urls.append(url)
        file.write(b'abc')
        return 3, 'a' * 64
    files = []
    monkeypatch.setattr(transfer, 'download', download)
    monkeypatch.setattr(transfer, 'put_file', lambda store, record, file: files.append(file))
    job = SimpleNamespace(sku='A', requirement_id='req', source_file_id='file', size=3, filename='file.pptx')
    for _ in range(2):
        transfer.transfer(job, SimpleNamespace(), None, lambda _: None)
    assert calls == ['A', 'A'] and all('token=fresh' in url for url in urls)
    assert all(file.closed for file in files)


def test_expired_signature_is_refreshed_on_retry(public_dns, monkeypatch):
    client_class = httpx.Client
    signatures = iter(('expired', 'fresh'))
    def fetch(sku):
        return {'list': [{'id': 'req', 'files': [{'id': 'file', 'filename': 'file.pdf', 'size': 3,
            'downloadUrl': '/api/files/file/download?token=' + next(signatures)}]}]}
    monkeypatch.setattr(source, 'fetch', fetch)
    def route(request):
        return httpx.Response(403 if request.url.params['token'] == 'expired' else 200, content=b'abc')
    monkeypatch.setattr(transfer.httpx, 'Client', lambda **kwargs: client_class(
        transport=httpx.MockTransport(route), **kwargs))
    stored = []
    monkeypatch.setattr(transfer, 'put_file', lambda store, record, file: stored.append(file.read()))
    job = SimpleNamespace(sku='A', requirement_id='req', source_file_id='file', size=3, filename='file.pdf')
    with pytest.raises(transfer.TransferError, match='签名已失效'):
        transfer.transfer(job, SimpleNamespace(), None, lambda _: None)
    transfer.transfer(job, SimpleNamespace(), None, lambda _: None)
    assert stored == [b'abc']


def test_stream_actual_size_limit_without_content_length(public_dns, monkeypatch):
    monkeypatch.setattr(transfer, 'MAX_UPLOAD_BYTES', 2)
    response = httpx.Response(200, stream=httpx.ByteStream(b'abc'))
    with httpx.Client(transport=httpx.MockTransport(lambda _: response)) as client:
        with pytest.raises(transfer.TransferError, match='500 MB'):
            transfer.download(client, source.ORIGIN + '/api/files/1/download?token=secret', BytesIO(), 3, lambda _: None)
