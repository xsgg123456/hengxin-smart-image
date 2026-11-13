"""Domestic API and the reused publisher communicate against isolated storage."""
from hashlib import sha256
import subprocess
import sys
import time
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.execution.models import ExecutionGate
from app.main import app
from app.models import Job
from app.modules.domestic_studio import skill_publication, skill_references
from app.modules.domestic_studio.installed_skills import DomesticInstalledSkills
from app.modules.domestic_studio.management_router import PUBLISH_SOCKET, get_catalog
from app.modules.domestic_studio.models import SkillExecutionReference, SkillPublicationAudit
from app.overseas.management import skill_cleanup, skill_publisher, skill_transfer_client
from app.overseas.management import skill_publication as shared_publication, installed_catalog
from app.overseas.management.skill_publisher import create_app
from app.overseas.management.skill_transfer_store import TransferStore, atomic_json
from app.resource_models import UserRecord
from files_helpers import files_env
from test_skill_initialization_recovery import CRASH

ROOT = '/api/v1/management/domestic-studio'
HEADERS = {'X-HX-Request': '1'}
DOCUMENT = b'---\nname: camera-test\ndescription: camera generator\n---\n# Camera\n'


@pytest.fixture
def service(files_env, tmp_path, monkeypatch):
    client, factory, _, identity = files_env
    root = tmp_path / 'domestic'
    root.mkdir()
    store = TransferStore(tmp_path / 'transfers', root)
    app.dependency_overrides[get_catalog] = lambda: DomesticInstalledSkills(root, protected=False)
    with factory.begin() as session:
        session.get(UserRecord, identity[0]).role = 'super_admin'
        if session.get(ExecutionGate, 1) is None:
            session.add(ExecutionGate(id=1))
    publisher = create_app(store, factory, publication=skill_publication, allow_maintenance=False)

    async def forward(method, path, actor, *, socket_path, body=None, content=None, params=None, key=None):
        assert socket_path == PUBLISH_SOCKET
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=publisher), base_url='http://publisher') as remote:
            response = await remote.request(method, path, json=body, content=content, params=params,
                headers={'X-Actor-Id': str(actor.id), **({'Idempotency-Key': key} if key else {})})
        if response.status_code >= 400:
            raise HTTPException(response.status_code, response.json()['detail'])
        return response.json()

    monkeypatch.setattr(skill_transfer_client, 'request', forward)
    return client, factory, identity, store


def stage(client, data=DOCUMENT):
    manifest = {'rootName': 'camera', 'entries': {
        'SKILL.md': {'size': len(data), 'sha256': sha256(data).hexdigest()}}}
    response = client.post(ROOT + '/skill-transfers', json=manifest, headers=HEADERS)
    assert response.status_code == 200, response.text
    transfer = response.json()['id']
    response = client.put(ROOT + f'/skill-transfers/{transfer}/files', params={'path': 'SKILL.md'},
                          content=data, headers=HEADERS)
    assert response.status_code == 200, response.text
    response = client.post(ROOT + f'/skill-transfers/{transfer}/validate', headers=HEADERS)
    assert response.status_code == 200, response.text
    return response.json()


def install(client, transfer):
    return client.post(ROOT + f"/skill-transfers/{transfer['id']}/install", headers=HEADERS,
                       json={'baseRelease': transfer['baseRelease']})


def deletion(client, item, package):
    return client.request('DELETE', ROOT + '/skills/' + item['id'], headers=HEADERS,
        json={'release': package['release'], 'checksum': package['checksum'], 'version': item['version']})


def test_upload_update_binding_delete_and_old_snapshot_remains_readable(service):
    client, factory, _, store = service
    first = stage(client)
    assert first['change'] == 'create'
    response = install(client, first)
    assert response.status_code == 200, response.text
    assert install(client, first).json() == response.json()
    item = client.get(ROOT + '/skills').json()['items'][0]
    assert item['enabled'] is False
    package = client.get(ROOT + '/skills/' + item['id'] + '/package').json()
    catalog = DomesticInstalledSkills(store.installed_root, protected=False)
    frozen = catalog.freeze(item['id'])
    assert catalog.frozen_package(frozen).files['SKILL.md'] == DOCUMENT
    toggle = ROOT + f"/skills/{item['id']}/availability"
    assert client.patch(toggle, json={'enabled': True, 'version': item['version']}, headers=HEADERS).status_code == 200
    bindings = {key: (item['id'] if key == 'camera' else None) for key in ('camera', 'case', 'product', 'scene', 'phone')}
    empty = dict.fromkeys(bindings)
    assert client.put(ROOT + '/bindings', json={'bindings': bindings, 'expected': empty}, headers=HEADERS).status_code == 200
    job_id = uuid4()
    with factory.begin() as session:
        job = Job(id=job_id, idempotency_key=str(job_id), payload_hash='a' * 64, value='{}',
                  kind=skill_references.JOB_KIND, status='running')
        session.add(job)
        session.flush()
        assert skill_references.freeze_and_pin(session, job, 'camera', catalog) == {'skill': frozen}
    item = client.get(ROOT + '/skills').json()['items'][0]
    assert deletion(client, item, package).status_code == 409
    second = stage(client, DOCUMENT + b'updated\n')
    assert second['change'] == 'update' and second['diff']['modified'] == ['SKILL.md']
    response = install(client, second)
    assert response.status_code == 200, response.text
    assert catalog.frozen_package(frozen).files['SKILL.md'] == DOCUMENT
    assert client.get(ROOT + '/skills').json()['items'][0]['enabled'] is True
    assert client.put(ROOT + '/bindings', json={'bindings': empty, 'expected': bindings}, headers=HEADERS).status_code == 200
    item = client.get(ROOT + '/skills').json()['items'][0]
    package = client.get(ROOT + '/skills/' + item['id'] + '/package').json()
    assert deletion(client, item, package).status_code == 409
    with factory.begin() as session:
        session.get(Job, job_id).status = 'succeeded'
    response = deletion(client, item, package)
    assert response.status_code == 200, response.text
    assert deletion(client, item, package).json() == response.json()
    assert client.get(ROOT + '/skills').json()['items'] == []
    assert catalog.frozen_package(frozen).files['SKILL.md'] == DOCUMENT
    with factory() as session:
        actions = list(session.scalars(select(SkillPublicationAudit.action).order_by(SkillPublicationAudit.created_at)))
    assert actions == ['skill.install', 'skill.update', 'skill.delete']
    with factory.begin() as session:
        session.delete(session.get(SkillExecutionReference, job_id))
        session.delete(session.get(Job, job_id))
    again = stage(client, DOCUMENT + b'new content\n')
    assert install(client, again).status_code == 200
    assert not (store.installed_root / 'packages' / frozen['name'] / frozen['checksum']).exists()


def test_unreferenced_delete_reclaims_verified_bytes_and_reports_net_change(service):
    client, _, _, store = service
    transfer = stage(client, DOCUMENT + b'content\n' * 16000)
    assert install(client, transfer).status_code == 200
    item = client.get(ROOT + '/skills').json()['items'][0]
    package = client.get(ROOT + '/skills/' + item['id'] + '/package').json()
    before = skill_cleanup.footprint(store)
    response = deletion(client, item, package)
    assert response.status_code == 200, response.text
    after = skill_cleanup.footprint(store)
    assert before > after
    assert response.json()['reclaimedBytes'] == before - after
    assert not (store.installed_root / 'packages' / item['name'] / package['checksum']).exists()


def test_unknown_studio_job_blocks_unsafe_skill_cleanup(service):
    client, factory, _, _ = service
    transfer = stage(client)
    assert install(client, transfer).status_code == 200
    item = client.get(ROOT + '/skills').json()['items'][0]
    package = client.get(ROOT + '/skills/' + item['id'] + '/package').json()
    with factory.begin() as session:
        identity = uuid4()
        session.add(Job(id=identity, idempotency_key=str(identity), payload_hash='a' * 64, value='{}',
                        kind=skill_references.JOB_KIND, status='running'))
    assert deletion(client, item, package).status_code == 503
    assert len(client.get(ROOT + '/skills').json()['items']) == 1


def test_publisher_recovers_first_install_crash_before_accepting_new_transfer(service):
    client, _, _, store = service
    crashed = subprocess.run([sys.executable, '-c', CRASH, str(store.installed_root), 'after-manifest'], check=False)
    assert crashed.returncode == 79
    assert client.get(ROOT + '/skills').status_code == 503
    assert client.get(ROOT + '/skill-transfers').status_code == 200
    assert client.get(ROOT + '/skills').json()['items'] == []
    assert install(client, stage(client)).status_code == 200


def test_publisher_rechecks_authorization_after_transfer_created(service):
    client, factory, identity, _ = service
    transfer = stage(client)
    with factory.begin() as session:
        session.get(UserRecord, identity[0]).role = 'designer'
    assert install(client, transfer).status_code == 403
    with factory.begin() as session:
        session.get(UserRecord, identity[0]).role = 'super_admin'
    assert install(client, transfer).status_code == 200
    assert client.post(ROOT + '/skill-transfers', json={}).status_code == 403


def test_uncommitted_publication_recovers_domestic_pointer(service):
    client, factory, _, store = service
    first = stage(client)
    assert install(client, first).status_code == 200
    previous, _ = installed_catalog.read_catalog(store.installed_root)
    second = stage(client, DOCUMENT + b'changed\n')
    replacement = dict(second['package'], entries=second['entries'], rootName=second['rootName'])
    newest = shared_publication.prepare_release(store, [replacement], second)
    atomic_json(store.installed_root / '.pending.json', {'audit': str(uuid4()), 'before': previous, 'after': newest})
    assert client.get(ROOT + '/skills').status_code == 503
    with factory() as session:
        skill_publication.recover(store, session)
    assert installed_catalog.read_catalog(store.installed_root)[0] == previous
    assert install(client, second).status_code == 200


def test_failed_database_commit_keeps_original_catalog_and_can_retry(service, monkeypatch):
    client, factory, identity, store = service
    first = stage(client)
    assert install(client, first).status_code == 200
    previous = installed_catalog.read_catalog(store.installed_root)
    second = stage(client, DOCUMENT + b'changed\n')
    with factory() as session:
        commit, failed = session.commit, []
        def fail_once():
            if not failed:
                failed.append(True)
                raise OSError('injected commit failure')
            return commit()
        monkeypatch.setattr(session, 'commit', fail_once)
        with pytest.raises(OSError, match='injected commit failure'):
            skill_publication.install(store, session, identity[0], second['id'], second['baseRelease'])
    assert installed_catalog.read_catalog(store.installed_root) == previous
    assert not (store.installed_root / '.pending.json').exists()
    assert install(client, second).status_code == 200


def test_stale_transfer_rejected_until_revalidated(service):
    client, _, _, _ = service
    first = stage(client)
    second = stage(client, DOCUMENT.replace(b'camera-test', b'other-skill'))
    assert install(client, first).status_code == 200
    assert install(client, second).status_code == 409
    response = client.post(ROOT + f"/skill-transfers/{second['id']}/validate", headers=HEADERS)
    assert response.status_code == 200
    assert install(client, response.json()).status_code == 200
    assert len(client.get(ROOT + '/skills').json()['items']) == 2


def test_committed_install_recovers_if_transfer_status_save_fails(service, monkeypatch):
    client, factory, _, store = service
    transfer = stage(client)
    save, failed = store.save, []
    def fail_once(state):
        if state['status'] == 'installed' and not failed:
            failed.append(True)
            raise OSError('injected status failure')
        return save(state)
    monkeypatch.setattr(store, 'save', fail_once)
    assert install(client, transfer).status_code == 503
    assert client.get(ROOT + '/skill-transfers/' + transfer['id']).json()['status'] == 'installed'
    assert install(client, transfer).status_code == 200
    with factory() as session:
        assert len(list(session.scalars(select(SkillPublicationAudit).where(
            SkillPublicationAudit.action == 'skill.install')))) == 1


def test_committed_deletion_retries_cleanup_without_browser_retry(service, monkeypatch):
    client, factory, identity, store = service
    transfer = stage(client)
    assert install(client, transfer).status_code == 200
    item = client.get(ROOT + '/skills').json()['items'][0]
    package = client.get(ROOT + '/skills/' + item['id'] + '/package').json()
    monkeypatch.setattr(skill_publisher, 'RECOVERY_INTERVAL', .02)
    remove, blocked = skill_cleanup.shutil.rmtree, [True]
    def fail(path, *args, **kwargs):
        if blocked[0] and path.name == package['checksum']:
            raise OSError('injected cleanup failure')
        return remove(path, *args, **kwargs)
    monkeypatch.setattr(skill_cleanup.shutil, 'rmtree', fail)
    publisher = create_app(store, factory, publication=skill_publication, allow_maintenance=False)
    with TestClient(publisher) as remote:
        response = remote.request('DELETE', '/skills/' + item['id'], headers={'X-Actor-Id': str(identity[0])},
            json={'release': package['release'], 'checksum': package['checksum'], 'version': item['version']})
        assert response.status_code == 503
        assert remote.get('/health').status_code == 503
        assert client.get(ROOT + '/skills').status_code == 503
        blocked[0] = False
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and (store.installed_root / '.pending.json').exists():
            time.sleep(.02)
        assert not (store.installed_root / '.pending.json').exists()
        assert remote.get('/health').json() == {'status': 'ok'}
        assert client.get(ROOT + '/skills').json()['items'] == []
        assert not (store.installed_root / 'packages' / item['name'] / package['checksum']).exists()
