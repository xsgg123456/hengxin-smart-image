from dataclasses import replace
from types import SimpleNamespace
from urllib.parse import urlencode
from uuid import uuid4

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.modules.files.delivery import FileDelivery
from app.modules.files import internal_delivery as module


def setup(monkeypatch, domain='originals', method='GET', marker='1'):
    identifier = uuid4()
    record = FileDelivery(identifier, 'private-images', f'{domain}/{identifier}', '原图.png', 'image/png', 20, 'a' * 64)
    settings = SimpleNamespace(media_internal_delivery_enabled=True, minio_bucket=record.bucket,
                               minio_endpoint='minio:9000', minio_secure=False)
    monkeypatch.setattr(module, 'get_settings', lambda: settings)
    request = Request({'type': 'http', 'method': method, 'headers': [(b'x-hengxin-media-gateway', marker.encode())]})
    calls = []
    def sign(r, verb, headers):
        calls.append((r, verb, headers))
        return f'http://minio:9000/{r.bucket}/{r.object_key}?' + urlencode({'X-Amz-Signature': 'test', **headers})
    return record, settings, request, SimpleNamespace(signed_delivery=sign), calls


@pytest.mark.parametrize('domain', ['originals', 'api-image-edits'])
@pytest.mark.parametrize('method', ['GET', 'HEAD'])
def test_internal_delivery_only_emits_safe_internal_header(monkeypatch, domain, method):
    record, settings, request, store, calls = setup(monkeypatch, domain, method)
    result = module.internal_delivery(record, store, request, domain, True)
    assert result.body == b'' and 'location' not in result.headers
    assert result.headers['cache-control'] == 'private, no-store'
    assert result.headers['x-accel-redirect'].startswith(f'/__hx_media/private-images/{domain}/{record.id}?')
    assert calls[0][1] == method
    assert calls[0][2]['response-content-disposition'].startswith('attachment;')
    settings.media_internal_delivery_enabled = False
    assert module.internal_delivery(record, store, request, domain) is None


@pytest.mark.parametrize('field,value', [('object_key', '../a'), ('object_key', 'originals/%2e%2e'),
                                        ('bucket', 'other'), ('object_key', 'skills/a.zip')])
def test_untrusted_file_path_never_signed(monkeypatch, field, value):
    record, _, request, store, calls = setup(monkeypatch)
    with pytest.raises(HTTPException) as error:
        module.internal_delivery(replace(record, **{field: value}), store, request, 'originals')
    assert error.value.status_code == 503 and not calls


@pytest.mark.parametrize('change', ['marker', 'endpoint', 'secure', 'method'])
def test_direct_or_misconfigured_delivery_fails_closed(monkeypatch, change):
    record, settings, request, store, calls = setup(monkeypatch, marker='' if change == 'marker' else '1',
                                                   method='POST' if change == 'method' else 'GET')
    if change == 'endpoint': settings.minio_endpoint = 'attacker.invalid'
    if change == 'secure': settings.minio_secure = True
    with pytest.raises(HTTPException): module.internal_delivery(record, store, request, 'originals')
    assert not calls


@pytest.mark.parametrize('target', ['http://attacker.invalid/a?q=signed', 'http://minio:9000/wrong?q=signed',
                                   'https://minio:9000/wrong?q=signed', 'http://minio:9000/a#secret'])
def test_sdk_target_is_revalidated_without_error_leak(monkeypatch, target):
    record, _, request, store, _ = setup(monkeypatch)
    store.signed_delivery = lambda *args: target
    with pytest.raises(HTTPException) as error:
        module.internal_delivery(record, store, request, 'originals')
    assert error.value.status_code == 503 and target not in str(error.value.detail)
