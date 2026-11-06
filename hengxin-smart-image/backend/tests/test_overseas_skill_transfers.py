"""Real API and publisher apps against isolated stores and a test database."""
import hashlib
from pathlib import Path
import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from app.core.config import get_settings
from app.overseas.management import installed_catalog, skill_transfer_client
from app.overseas.management.models import Audit, InstalledSkillAvailability
from app.overseas.management.skill_publisher import create_app
from app.overseas.management.skill_transfer_store import TransferStore
from test_overseas_tasks import overseas, setup, ROOT
from test_overseas_auth import HEADERS

URL = ROOT + '/management'
DOCUMENT = b'---\nname: folder-test\ndescription: complete folder\n---\n# Folder title\n'


@pytest.fixture
def transfers(overseas, tmp_path, monkeypatch):
    client, factory, actor, _ = setup(overseas, ('super_admin',))
    get_settings().skill_toggle_owner_id = actor
    store = TransferStore(tmp_path / 'transfers', Path(get_settings().local_skill_root))
    publisher = create_app(store, factory)

    async def forward(method, path, member, *, body=None, content=None, params=None, key=None):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=publisher), base_url='http://publisher') as remote:
            response = await remote.request(method, path, json=body, content=content, params=params,
                headers={'X-Actor-Id': str(member.id), **({'Idempotency-Key': key} if key else {})})
        if response.status_code >= 400:
            raise HTTPException(response.status_code, response.json()['detail'])
        return response.json()

    monkeypatch.setattr(skill_transfer_client, 'request', forward)
    return client, factory, actor, store


def manifest(files, directories=('empty/', 'assets/')):
    return {**{path: {'directory': True} for path in directories},
            **{path: {'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()} for path, data in files.items()}}


def upload(client, files=None, key=None, root_name='原始文件夹'):
    files = files or {'SKILL.md': DOCUMENT, 'assets/data.bin': bytes(range(256)) + b'\x00\xff'}
    response = client.post(URL + '/skill-transfers', headers={**HEADERS, **({'Idempotency-Key': key} if key else {})},
                           json={'rootName': root_name, 'entries': manifest(files)})
    assert response.status_code == 200, response.text
    transfer = response.json()
    for path, data in files.items():
        response = client.put(URL + f"/skill-transfers/{transfer['id']}/files", params={'path': path},
                              headers={**HEADERS, 'Content-Type': 'application/octet-stream'}, content=data)
        assert response.status_code == 200, response.text
    response = client.post(URL + f"/skill-transfers/{transfer['id']}/validate", headers=HEADERS)
    assert response.status_code == 200, response.text
    return response.json(), files


def install(client, transfer):
    return client.post(URL + f"/skill-transfers/{transfer['id']}/install", headers=HEADERS,
                       json={'baseRelease': transfer['baseRelease']})


def deletion(client, item, package):
    return client.request('DELETE', URL + '/skills/' + item['id'], headers=HEADERS,
        json={'release': package['release'], 'checksum': package['checksum'], 'version': item['version']})


def test_binary_empty_directories_original_name_roundtrip_and_default_disabled(transfers):
    client, factory, _, _ = transfers
    transfer, files = upload(client, key='folder-1')
    assert transfer['change'] == 'create' and transfer['package']['displayName'] == 'Folder title'
    response = install(client, transfer)
    assert response.status_code == 200, response.text
    assert install(client, transfer).json() == response.json()
    item = client.get(URL + '/skills').json()['items'][0]
    assert item['enabled'] is False and item['platforms'] == []
    package = client.get(URL + '/skills/' + item['id'] + '/package').json()
    assert package['rootName'] == '原始文件夹' and package['entries'] == manifest(files)
    for path, data in files.items():
        output = client.get(URL + '/skills/' + item['id'] + '/files', params={'release': package['release'], 'path': path})
        assert output.status_code == 200 and output.content == data
    assert client.get(URL + '/skill-transfers').json()['items'][0]['status'] == 'installed'
    with factory() as session:
        assert session.scalar(select(Audit)).action == 'skill.install'


def test_update_diff_retains_state_reclaims_unreferenced_old_bytes(transfers):
    client, factory, _, _ = transfers
    first, old_files = upload(client)
    assert install(client, first).status_code == 200
    item = client.get(URL + '/skills').json()['items'][0]
    frozen = installed_catalog.freeze(item['id'])
    with factory.begin() as session:
        row = session.get(InstalledSkillAvailability, 'folder-test')
        row.enabled, row.platforms = True, ['Amazon']
    second, _ = upload(client, {'SKILL.md': DOCUMENT + b'new', 'assets/new.bin': b'\xffnew'})
    assert second['change'] == 'update'
    assert second['diff'] == {'added': ['assets/new.bin'], 'removed': ['assets/data.bin'], 'modified': ['SKILL.md']}
    assert install(client, second).status_code == 200
    current = client.get(URL + '/skills').json()['items'][0]
    assert current['enabled'] and current['platforms'] == ['Amazon']
    assert installed_catalog.frozen_item(frozen)[1]['checksum'] == frozen['checksum']
    with pytest.raises(FileNotFoundError):
        installed_catalog.frozen_package(frozen)
    download = client.get(URL + '/skills/' + item['id'] + '/files', params={
        'release': frozen['installedRelease'], 'path': 'assets/data.bin'})
    assert download.status_code == 410


def test_identical_delete_last_conflicts_replay_and_reinstall(transfers):
    client, factory, _, _ = transfers
    transfer, _ = upload(client)
    assert install(client, transfer).status_code == 200
    same, _ = upload(client)
    assert same['change'] == 'identical' and install(client, same).status_code == 200
    item = client.get(URL + '/skills').json()['items'][0]
    package = client.get(URL + '/skills/' + item['id'] + '/package').json()
    with factory.begin() as session:
        row = session.get(InstalledSkillAvailability, 'folder-test')
        row.version += 1
    assert deletion(client, item, package).status_code == 409
    item = client.get(URL + '/skills').json()['items'][0]
    result = deletion(client, item, package)
    assert result.status_code == 200, result.text
    assert deletion(client, item, package).json() == result.json()
    assert client.get(URL + '/skills').json()['items'] == []
    assert type(result.json()['reclaimedBytes']) is int and result.json()['reclaimedBytes'] >= 0
    with pytest.raises(FileNotFoundError):
        installed_catalog.frozen_package({'name': 'folder-test', 'installedRelease': package['release'],
                                         'checksum': package['checksum']})
    again, _ = upload(client)
    assert again['change'] == 'create' and install(client, again).status_code == 200
    item = client.get(URL + '/skills').json()['items'][0]
    assert not item['enabled'] and item['platforms'] == []


def test_permissions_download_managers_upload_owner_only_and_browser_guard(transfers):
    client, _, _, _ = transfers
    transfer, _ = upload(client)
    assert install(client, transfer).status_code == 200
    item = client.get(URL + '/skills').json()['items'][0]
    get_settings().skill_toggle_owner_id = None
    assert client.get(URL + '/skills/' + item['id'] + '/package').status_code == 200
    assert client.get(URL + '/skill-transfers').status_code == 403
    assert client.post(URL + '/skill-transfers', json={}).status_code == 403


@pytest.mark.parametrize('entries', [
    {'SKILL.md': {'size': 67108865, 'sha256': 'a' * 64}},
    {'../SKILL.md': {'size': 1, 'sha256': 'a' * 64}},
    {'SKILL.md': {'size': 1, 'sha256': 'a' * 64}, 'assets/a': {'size': 1, 'sha256': 'b' * 64}},
    {'SKILL.md': {'size': 1, 'sha256': 'a' * 64}, 'Assets/': {'directory': True}, 'assets/': {'directory': True}},
    {**{str(i) + '/': {'directory': True} for i in range(2000)}, 'SKILL.md': {'size': 1, 'sha256': 'a' * 64}},
    {**{str(i): {'size': 1, 'sha256': 'a' * 64} for i in range(1000)}, 'SKILL.md': {'size': 1, 'sha256': 'a' * 64}},
    {**{str(i): {'size': 67108864, 'sha256': 'a' * 64} for i in range(4)}, 'SKILL.md': {'size': 1, 'sha256': 'a' * 64}},
])
def test_limits_and_unsafe_manifests_rejected_atomically(transfers, entries):
    client, _, _, store = transfers
    response = client.post(URL + '/skill-transfers', headers=HEADERS, json={'rootName': 'folder', 'entries': entries})
    assert response.status_code == 422, response.text
    assert list(store.path.iterdir()) == []
