from uuid import uuid4

import pytest

from app.execution.models import ExecutionGate
from app.main import app
from app.modules.domestic_studio.management_router import get_catalog
from app.modules.domestic_studio import management_router
from app.modules.domestic_studio.policy import WORKSPACES
from app.modules.domestic_studio.installed_skills import DomesticInstalledSkills
from app.resource_models import UserRecord
from files_helpers import files_env
from test_domestic_installed_skills import install_fixture


ROOT = '/api/v1/management/domestic-studio'
HEADERS = {'X-HX-Request': '1'}


@pytest.fixture
def management(files_env, tmp_path):
    client, factory, _, identity = files_env
    root = tmp_path / 'domestic'
    root.mkdir()
    install_fixture(tmp_path, root)
    catalog = DomesticInstalledSkills(root, protected=False)
    app.dependency_overrides[get_catalog] = lambda: catalog
    with factory.begin() as session:
        session.get(UserRecord, identity[0]).role = 'super_admin'
        if session.get(ExecutionGate, 1) is None:
            session.add(ExecutionGate(id=1))
    yield client, factory, identity, catalog


def empty():
    return dict.fromkeys(WORKSPACES)


def bind(client, wanted, expected=None):
    expected = client.get(ROOT + '/bindings').json()['bindings'] if expected is None else expected
    return client.put(ROOT + '/bindings', json={'bindings': wanted, 'expected': expected}, headers=HEADERS)


def test_admin_can_bind_only_an_installed_and_enabled_skill(management):
    client, _, _, _ = management
    item = client.get(ROOT + '/skills').json()['items'][0]
    assert item['enabled'] is False
    wanted = empty() | {'camera': item['id']}
    assert bind(client, wanted).status_code == 422
    assert client.get(ROOT + '/bindings').json()['bindings'] == empty()
    toggle = ROOT + f"/skills/{item['id']}/availability"
    assert client.patch(toggle, json={'enabled': True, 'version': 1}, headers=HEADERS).json()['items'][0]['enabled'] is True
    assert client.patch(toggle, json={'enabled': False, 'version': 1}, headers=HEADERS).status_code == 409
    assert bind(client, wanted).json()['bindings'] == wanted
    assert client.patch(toggle, json={'enabled': False, 'version': 2}, headers=HEADERS).status_code == 409
    assert bind(client, empty()).status_code == 200
    assert client.patch(toggle, json={'enabled': False, 'version': 2}, headers=HEADERS).json()['items'][0]['enabled'] is False


@pytest.mark.parametrize('role', ['operator', 'designer', 'design_manager'])
def test_management_endpoints_reject_non_admin_roles(management, role):
    client, factory, identity, _ = management
    with factory.begin() as session:
        session.get(UserRecord, identity[0]).role = role
    assert client.get(ROOT + '/skills').status_code == 403
    assert client.get(ROOT + '/bindings').status_code == 403
    assert client.put(ROOT + '/bindings', json=empty(), headers=HEADERS).status_code == 403
    assert client.patch(ROOT + f'/skills/{uuid4()}/availability', json={'enabled': True, 'version': 1}, headers=HEADERS).status_code == 403


def test_no_session_and_missing_browser_header_are_rejected(management):
    client, _, identity, _ = management
    assert client.put(ROOT + '/bindings', json=empty()).status_code == 403
    identity[0] = uuid4()
    assert client.get(ROOT + '/skills').status_code == 401
    assert client.put(ROOT + '/bindings', json=empty(), headers=HEADERS).status_code == 401


def test_binding_payload_requires_all_five_and_no_extra_keys(management):
    client, _, _, _ = management
    assert client.put(ROOT + '/bindings', json={'camera': None}, headers=HEADERS).status_code == 422
    assert client.put(ROOT + '/bindings', json=empty() | {'other': None}, headers=HEADERS).status_code == 422
    assert client.get(ROOT + '/bindings').json()['bindings'] == empty()


def test_stale_binding_snapshot_returns_conflict_without_losing_other_change(management):
    client, _, _, _ = management
    item = client.get(ROOT + '/skills').json()['items'][0]
    assert client.patch(ROOT + f"/skills/{item['id']}/availability", json={'enabled': True, 'version': 1}, headers=HEADERS).status_code == 200
    original = client.get(ROOT + '/bindings').json()['bindings']
    assert bind(client, original | {'camera': item['id']}, original).status_code == 200
    response = bind(client, original | {'case': item['id']}, original)
    assert response.status_code == 409
    assert client.get(ROOT + '/bindings').json()['bindings'] == original | {'camera': item['id']}


def test_admin_can_download_verified_package_and_file(management):
    client, _, _, _ = management
    item = client.get(ROOT + '/skills').json()['items'][0]
    base = ROOT + f"/skills/{item['id']}"
    package = client.get(base + '/package')
    assert package.status_code == 200
    manifest = package.json()
    assert manifest['name'] == 'camera-test'
    response = client.get(base + '/files', params={'release': manifest['release'], 'path': 'SKILL.md'})
    assert response.status_code == 200
    assert b'name: camera-test' in response.content
    assert client.get(base + '/files', params={'release': manifest['release'], 'path': '../SKILL.md'}).status_code == 404
    assert client.get(base + '/package').status_code == 200


def test_transfer_proxy_uses_only_domestic_socket_and_rechecks_permissions(management, monkeypatch):
    client, factory, identity, _ = management
    calls = []

    async def forward(method, path, actor, **kwargs):
        content = kwargs.pop('content', None)
        if content is not None:
            kwargs['bytes'] = b''.join([chunk async for chunk in content])
        calls.append((method, path, actor.id, kwargs))
        return {'ok': True}

    monkeypatch.setattr(management_router.publisher, 'request', forward)
    transfer, skill = str(uuid4()), str(uuid4())
    manifest = {'rootName': 'camera', 'entries': {'SKILL.md': {'size': 1, 'sha256': 'a' * 64}}}
    assert client.post(ROOT + '/skill-transfers', json=manifest, headers=HEADERS).status_code == 200
    assert client.put(ROOT + f'/skill-transfers/{transfer}/files', params={'path': 'SKILL.md'},
                      content=b'x', headers=HEADERS).status_code == 200
    assert client.post(ROOT + f'/skill-transfers/{transfer}/validate', headers=HEADERS).status_code == 200
    assert client.post(ROOT + f'/skill-transfers/{transfer}/install', json={'baseRelease': None}, headers=HEADERS).status_code == 200
    assert client.request('DELETE', ROOT + f'/skills/{skill}', json={
        'release': 'b' * 64, 'checksum': 'c' * 64, 'version': 1}, headers=HEADERS).status_code == 200
    assert all(row[2] == identity[0] and row[3]['socket_path'] == management_router.PUBLISH_SOCKET for row in calls)
    assert calls[1][3]['bytes'] == b'x' and calls[1][3]['params'] == {'path': 'SKILL.md'}
    assert client.post(ROOT + '/skill-transfers', json=manifest).status_code == 403
    with factory.begin() as session:
        session.get(UserRecord, identity[0]).role = 'designer'
    assert client.get(ROOT + '/skill-transfers').status_code == 403
    assert len(calls) == 5


def test_non_admin_cannot_download_skill_files(management):
    client, factory, identity, _ = management
    item = client.get(ROOT + '/skills').json()['items'][0]
    package = client.get(ROOT + f"/skills/{item['id']}/package").json()
    with factory.begin() as session:
        session.get(UserRecord, identity[0]).role = 'designer'
    assert client.get(ROOT + f"/skills/{item['id']}/package").status_code == 403
    assert client.get(ROOT + f"/skills/{item['id']}/files", params={'release': package['release'], 'path': 'SKILL.md'}).status_code == 403


def test_unconfigured_catalog_is_not_treated_as_empty(management):
    client, _, _, _ = management
    app.dependency_overrides.pop(get_catalog)
    assert client.get(ROOT + '/skills').status_code == 503
