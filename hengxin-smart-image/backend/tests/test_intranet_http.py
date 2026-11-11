"""Production intranet exception must not weaken public-origin or browser guards."""
from http.cookies import SimpleCookie

from fastapi import Depends, FastAPI, Request, Response
from fastapi.testclient import TestClient
import pytest

from app.core import browser_auth
from app.core.config import Settings
from app.overseas.config import OverseasSettings
from test_overseas_configuration import FAKE_OVERSEAS


def settings_for(origin, *, settings_type=Settings, **overrides):
    resources = {name.lower(): value for name, value in FAKE_OVERSEAS.items()}
    return settings_type(
        _env_file=None, **resources, app_env='production',
        identity_service_url='http://127.0.0.1:8081', identity_service_key='a' * 32,
        identity_public_origin=origin, **overrides,
    )


@pytest.mark.parametrize('settings_type', [Settings, OverseasSettings])
@pytest.mark.parametrize('origin', [
    'http://10.0.0.1', 'http://10.255.255.254:80',
    'http://172.16.0.1:8080', 'http://172.31.255.254',
    'http://192.168.0.1', 'http://192.168.255.254:65535/',
    'http://192.168.1.245:8080',
])
def test_production_http_requires_explicit_opt_in(origin, settings_type):
    with pytest.raises(ValueError, match='must use HTTPS'):
        settings_for(origin, settings_type=settings_type)
    settings = settings_for(origin, settings_type=settings_type, allow_intranet_http=True)
    assert settings.app_env == 'production'
    assert settings.intranet_http_enabled
    assert not settings.enable_dev_identity
    assert not settings.enable_test_jobs


@pytest.mark.parametrize('origin', [
    'http://9.255.255.255', 'http://11.0.0.0',
    'http://172.15.255.255', 'http://172.32.0.0',
    'http://192.167.255.255', 'http://192.169.0.0',
    'http://8.8.8.8', 'http://127.0.0.1', 'http://localhost:8080',
    'http://intranet.example', 'http://192.168.1.245.example',
    'http://[::1]', 'http://[fd00::1]', 'http://[::ffff:192.168.1.245]',
    'http://169.254.1.1', 'http://100.64.0.1', 'http://192.0.2.1', 'http://0.0.0.0',
    'http://192.168.001.245', 'http://3232236021', 'http://0xc0a801f5',
    'http://192.168.1.245:0', 'http://192.168.1.245:65536',
    'http://192.168.1.245:', '\x00http://192.168.1.245',
    'http://192.168.1.245:not-a-port', 'http://user@192.168.1.245',
    'http://@192.168.1.245', 'http://192.168.1.245/private',
    'http://192.168.1.245?redirect=1', 'http://192.168.1.245#fragment',
    'http://192.168.1.245\n', 'ftp://192.168.1.245',
])
def test_opt_in_rejects_non_rfc1918_or_malformed_origins(origin):
    with pytest.raises(ValueError):
        settings_for(origin, allow_intranet_http=True)


@pytest.mark.parametrize('flag', ['enable_dev_identity', 'enable_test_jobs'])
def test_http_opt_in_does_not_bypass_production_guards(flag):
    with pytest.raises(ValueError, match='forbidden in production'):
        settings_for('http://192.168.1.245:8080', allow_intranet_http=True, **{flag: True})


@pytest.mark.parametrize('origin,enabled,secure', [
    ('https://app.example', False, True),
    ('https://app.example', True, True),
    ('https://192.168.1.245:8080', True, True),
    ('http://192.168.1.245:8080', True, False),
])
@pytest.mark.parametrize('name,path', [('hx_session', '/'), ('hx_overseas_session', '/api/overseas/v1')])
def test_business_cookie_keeps_scope_and_protections(monkeypatch, origin, enabled, secure, name, path):
    settings = settings_for(origin, allow_intranet_http=enabled)
    monkeypatch.setattr(browser_auth, 'get_settings', lambda: settings)
    response = Response()
    browser_auth.set_business_cookie(response, name, 'test-token', path)
    cookie = SimpleCookie(response.headers['set-cookie'])[name]
    assert bool(cookie['secure']) == secure
    assert cookie['httponly']
    assert cookie['samesite'] == 'lax'
    assert cookie['path'] == path
    assert cookie['max-age'] == str(settings.auth_session_ttl_seconds)
    assert not cookie['domain']


def test_intranet_cookie_round_trip_and_origin_guard(monkeypatch):
    origin = 'http://192.168.1.245:8080'
    settings = settings_for(origin, allow_intranet_http=True)
    monkeypatch.setattr(browser_auth, 'get_settings', lambda: settings)
    app = FastAPI()

    @app.post('/session', dependencies=[Depends(browser_auth.browser_request)])
    def session(response: Response):
        browser_auth.set_business_cookie(response, 'hx_session', 'test-token', '/')
        return {'ok': True}

    @app.get('/session')
    def current_session(request: Request):
        return {'token': request.cookies.get('hx_session')}

    with TestClient(app, base_url=origin) as client:
        assert client.post('/session', headers={'Origin': origin}).status_code == 403
        for untrusted in ('http://192.168.1.246:8080', 'http://192.168.1.245:8081',
                          'https://192.168.1.245:8080', 'http://attacker.example', 'null'):
            response = client.post('/session', headers={'Origin': untrusted, 'X-HX-Request': '1'})
            assert response.status_code == 403
            assert 'set-cookie' not in response.headers
        response = client.post('/session', headers={'Origin': origin, 'X-HX-Request': '1'})
        assert response.status_code == 200
        assert client.get('/session').json() == {'token': 'test-token'}


def test_overseas_opt_in_requires_own_prefixed_environment(monkeypatch):
    for name, value in FAKE_OVERSEAS.items():
        monkeypatch.setenv('OVERSEAS_' + name, value)
    monkeypatch.setenv('OVERSEAS_APP_ENV', 'production')
    monkeypatch.setenv('OVERSEAS_IDENTITY_SERVICE_URL', 'http://127.0.0.1:8081')
    monkeypatch.setenv('OVERSEAS_IDENTITY_SERVICE_KEY', 'a' * 32)
    monkeypatch.setenv('OVERSEAS_IDENTITY_PUBLIC_ORIGIN', 'http://192.168.1.245:8080')
    monkeypatch.setenv('ALLOW_INTRANET_HTTP', 'true')
    monkeypatch.delenv('OVERSEAS_ALLOW_INTRANET_HTTP', raising=False)
    with pytest.raises(ValueError, match='must use HTTPS'):
        OverseasSettings()
    monkeypatch.setenv('OVERSEAS_ALLOW_INTRANET_HTTP', 'true')
    assert OverseasSettings().intranet_http_enabled
