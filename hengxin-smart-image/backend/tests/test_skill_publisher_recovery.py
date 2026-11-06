"""A restarted/reloaded browser need not retain a failed deletion's request body."""
import time
import pytest
from fastapi.testclient import TestClient

from app.overseas.management import skill_cleanup, skill_publisher, installed_catalog
from test_overseas_skill_transfers import transfers, overseas, upload, install, URL


def test_pending_cleanup_recovers_without_original_delete_retry(transfers, monkeypatch):
    client, factory, actor, store = transfers
    transfer, _ = upload(client)
    assert install(client, transfer).status_code == 200
    item = client.get(URL + '/skills').json()['items'][0]
    package = client.get(URL + '/skills/' + item['id'] + '/package').json()
    monkeypatch.setattr(skill_publisher, 'RECOVERY_INTERVAL', .02)
    original = skill_cleanup.shutil.rmtree
    blocked = [True]
    def fail(path, *args, **kwargs):
        if blocked[0] and path.name == package['checksum']:
            raise OSError('injected temporary storage failure')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(skill_cleanup.shutil, 'rmtree', fail)
    with TestClient(skill_publisher.create_app(store, factory)) as publisher:
        response = publisher.request('DELETE', '/skills/' + item['id'], headers={'X-Actor-Id': str(actor)},
            json=dict(release=package['release'], checksum=package['checksum'], version=item['version']))
        assert response.status_code == 503
        assert publisher.get('/health').status_code == 503
        assert client.get(URL + '/skills').status_code == 503
        blocked[0] = False
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and (store.installed_root / '.pending.json').exists():
            time.sleep(.02)
        assert not (store.installed_root / '.pending.json').exists()
        assert publisher.get('/health').json() == {'status': 'ok'}
        # A fresh page can now load the catalog using its ordinary read route.
        assert client.get(URL + '/skills').json()['items'] == []
        with pytest.raises(FileNotFoundError):
            installed_catalog.frozen_package(dict(name=item['name'], installedRelease=package['release'],
                                                  checksum=package['checksum']))
