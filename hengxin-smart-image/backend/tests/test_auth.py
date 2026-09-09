from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select

from app.core.config import Settings, get_settings
from app.main import app
from app.modules.auth.dependencies import get_identity_id
from app.modules.auth.dev_identity import seed_dev_identity
from app.modules.auth.permissions import authorize
from app.modules.files.deletions import logical_delete
from app.resource_models import DeletionRecord, UserRecord
from files_helpers import files_env, image_bytes


def test_production_guard():
    with pytest.raises(ValidationError, match='forbidden'):
        Settings(app_env='production', enable_dev_identity=True)
    assert not Settings().enable_dev_identity


def test_auth_me_fixed_identity_ignores_client_headers(files_env, monkeypatch):
    client, _, _, identity = files_env
    app.dependency_overrides.pop(get_identity_id)
    monkeypatch.setenv('ENABLE_DEV_IDENTITY', 'true')
    monkeypatch.setenv('DEV_USER_ID', str(identity[0]))
    get_settings.cache_clear()
    try:
        response = client.get('/api/v1/auth/me', headers={
            'X-User-ID': str(uuid4()), 'X-Role': 'super_admin', 'Authorization': 'Bearer forged',
        })
        assert response.status_code == 200
        assert response.json() == {'id': str(identity[0]), 'name': '测试操作者',
                                  'role': 'operator', 'status': 'active'}
    finally:
        get_settings.cache_clear()


def test_anonymous_cannot_forge_identity_or_download(files_env):
    client, _, _, _ = files_env
    picture = client.post('/api/v1/files', files={'file': ('x.png', image_bytes(), 'image/png')}).json()
    app.dependency_overrides.pop(get_identity_id)
    for path in ['/api/v1/auth/me', picture['url'], '/api/v1/files/' + picture['fileId']]:
        response = client.get(path, headers={'X-User-ID': 'fake', 'X-Role': 'super_admin'})
        assert response.status_code == 401
    assert client.post('/api/v1/files', files={'file': ('x.png', image_bytes(), 'image/png')}).status_code == 401


@pytest.mark.parametrize('status,role', [('pending', None), ('disabled', 'super_admin'), ('active', None)])
def test_unauthorized_status_denied(files_env, status, role):
    client, factory, _, identity = files_env
    with factory.begin() as session:
        user = session.get(UserRecord, identity[0])
        user.status, user.role = status, role
    assert client.get('/api/v1/auth/me').status_code == 403
    assert client.post('/api/v1/files', files={'file': ('x.png', image_bytes(), 'image/png')}).status_code == 403


def test_production_cannot_reuse_historical_development_identity(files_env, monkeypatch):
    client, _, _, _ = files_env
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('ENABLE_TEST_JOBS', 'false')
    get_settings.cache_clear()
    try:
        assert client.get('/api/v1/auth/me').status_code == 401
    finally:
        get_settings.cache_clear()


@pytest.mark.parametrize('role', ['super_admin', 'design_manager', 'designer', 'operator'])
def test_role_matrix(role):
    user = SimpleNamespace(status='active', role=role)
    assert authorize(user) is user
    for permission, allowed in [('manage_system', role == 'super_admin'),
                                ('all_usage', role in ('super_admin', 'design_manager'))]:
        if allowed:
            assert authorize(user, permission) is user
        else:
            with pytest.raises(HTTPException) as error:
                authorize(user, permission)
            assert error.value.status_code == 403


def test_seed_never_resets_existing_role_status(files_env, monkeypatch):
    _, factory, _, identity = files_env
    monkeypatch.setattr('app.modules.auth.dev_identity.session_factory', lambda: factory)
    monkeypatch.setenv('ENABLE_DEV_IDENTITY', 'true')
    monkeypatch.setenv('DEV_USER_ID', str(identity[0]))
    get_settings.cache_clear()
    try:
        with factory.begin() as session:
            user = session.get(UserRecord, identity[0])
            user.role, user.status = 'designer', 'disabled'
        seed_dev_identity()
        with factory() as session:
            user = session.get(UserRecord, identity[0])
            assert (user.role, user.status) == ('designer', 'disabled')
        with factory.begin() as session:
            session.get(UserRecord, identity[0]).identity_source = 'dingtalk'
        with pytest.raises(RuntimeError, match='conflicts'):
            seed_dev_identity()
    finally:
        get_settings.cache_clear()


def test_logical_delete_preserves_actual_actor_and_is_idempotent(files_env):
    _, factory, _, identity = files_env
    resource = SimpleNamespace(id=uuid4(), owner_id=uuid4(), deleted_at=None)
    with factory.begin() as session:
        user = session.get(UserRecord, identity[0])
        receipt = logical_delete(session, resource, 'task', user)
        assert receipt.operator_id == identity[0] != resource.owner_id
        assert receipt.resource_id == resource.id
        assert logical_delete(session, resource, 'task', user) is None
    with factory() as session:
        assert len(session.scalars(select(DeletionRecord)).all()) == 1
