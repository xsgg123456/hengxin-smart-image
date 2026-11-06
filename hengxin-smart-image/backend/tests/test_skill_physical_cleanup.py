"""Real deletion failure recovery, byte accounting and bounded cleanup targets."""
import json
import os
from pathlib import Path
import shutil
import subprocess
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.overseas.management import skill_cleanup
from app.overseas.management.models import Audit
from test_overseas_skill_transfers import URL, deletion, install, overseas, transfers, upload


def installed(transfers):
    client, factory, actor, store = transfers
    transfer, files = upload(client)
    assert install(client, transfer).status_code == 200
    item = client.get(URL + '/skills').json()['items'][0]
    package = client.get(URL + '/skills/' + item['id'] + '/package').json()
    return client, factory, store, transfer, item, package


def test_partial_rmtree_failure_is_503_recoverable_and_idempotent(transfers, monkeypatch):
    client, factory, store, transfer, item, package = installed(transfers)
    central = store.installed_root / 'packages' / 'folder-test' / package['checksum']
    staging = store.directory(transfer['id']) / 'package'
    # Model a pre-upgrade installed transfer which still has its full upload tree.
    assert not staging.exists()
    shutil.copytree(central, staging)
    before = skill_cleanup.footprint(store)
    original, removed = shutil.rmtree, []

    def interrupted(path, *args, **kwargs):
        if Path(path) == staging:
            (staging / 'assets' / 'data.bin').unlink(missing_ok=True)
            raise OSError('injected partial disk failure')
        original(path, *args, **kwargs)
        removed.append(Path(path))

    monkeypatch.setattr(skill_cleanup.shutil, 'rmtree', interrupted)
    first = deletion(client, item, package)
    assert first.status_code == 503, first.text
    assert central in removed and not central.exists()
    assert staging.exists() and not (staging / 'assets' / 'data.bin').exists()
    journal = store.installed_root / '.pending.json'
    pending = json.loads(journal.read_text())
    assert pending['cleanup']['beforeBytes'] == before
    with factory() as session:
        audit = session.scalar(select(Audit).where(Audit.action == 'skill.delete'))
        assert not audit.after.get('cleanupComplete')
    monkeypatch.setattr(skill_cleanup.shutil, 'rmtree', original)
    second = deletion(client, item, package)
    assert second.status_code == 200, second.text
    assert not staging.exists() and not central.exists() and not journal.exists()
    assert second.json()['reclaimedBytes'] == max(0, before - skill_cleanup.footprint(store))
    assert second.json()['reclaimedBytes'] > 0
    after = skill_cleanup.footprint(store)
    assert deletion(client, item, package).json() == second.json()
    assert skill_cleanup.footprint(store) == after
    with factory() as session:
        audits = list(session.scalars(select(Audit).where(Audit.action == 'skill.delete')))
        assert len(audits) == 1 and audits[0].after['cleanupComplete'] is True


@pytest.mark.parametrize('scope,path', [
    ('library', '../outside'), ('library', 'packages/../' + 'a' * 64),
    ('library', 'packages/folder-test/../../outside'), ('library', '/outside'),
    ('library', 'packages/folder-test/' + 'a' * 64 + '/nested'),
    ('transfers', '../package'), ('transfers', str(uuid4()) + '/state.json'),
    ('unknown', 'packages/folder-test/' + 'a' * 64),
])
def test_cleanup_validates_all_paths_before_removing_any(transfers, scope, path):
    _, _, store, _, _, package = installed(transfers)
    valid = dict(scope='library', path='packages/folder-test/' + package['checksum'])
    central = store.installed_root / valid['path']
    expected = (central / 'SKILL.md').read_bytes()
    journal = dict(schema=1, targets=[valid, dict(scope=scope, path=path)],
                   beforeBytes=skill_cleanup.footprint(store), historyBytes=0)
    with pytest.raises(ValueError):
        skill_cleanup.execute(store, journal)
    assert (central / 'SKILL.md').read_bytes() == expected


def test_cleanup_rejects_hardlinked_file_without_touching_original(transfers, tmp_path):
    _, _, store, _, _, package = installed(transfers)
    central = store.installed_root / 'packages' / 'folder-test' / package['checksum']
    outside = tmp_path / 'private-do-not-delete.bin'
    outside.write_bytes(b'private independent file')
    os.link(outside, central / 'linked.bin')
    try:
        with pytest.raises(ValueError, match='shared'):
            skill_cleanup.target(store, dict(scope='library',
                path='packages/folder-test/' + package['checksum']))
        assert outside.read_bytes() == b'private independent file'
        assert (central / 'SKILL.md').is_file()
    finally:
        (central / 'linked.bin').unlink()


def test_cleanup_rejects_directory_link_outside_approved_root(transfers, tmp_path):
    _, _, store, _, _, package = installed(transfers)
    outside = tmp_path / 'outside'
    outside.mkdir()
    marker = outside / 'keep.txt'
    marker.write_bytes(b'keep me')
    linked = store.installed_root / 'packages' / 'linked-skill'
    try:
        linked.symlink_to(outside, target_is_directory=True)
    except OSError as error:
        if os.name != 'nt':
            pytest.skip('OS does not permit creating symlinks: ' + str(error))
        # Windows junctions require no symlink privilege and must be rejected too.
        result = subprocess.run(['cmd.exe', '/c', 'mklink', '/J', str(linked), str(outside)],
                                capture_output=True)
        assert result.returncode == 0, result.stderr.decode(errors='replace')
    try:
        with pytest.raises(ValueError):
            skill_cleanup.target(store, dict(scope='library',
                path='packages/linked-skill/' + package['checksum']))
        assert marker.read_bytes() == b'keep me'
    finally:
        if linked.is_symlink():
            linked.unlink()
        else:
            assert linked.parent == store.installed_root / 'packages'
            os.rmdir(linked)
