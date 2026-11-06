"""Original net savings survive failures before the publication journal exists."""
import json
import os

import pytest
from sqlalchemy import select

from app.overseas.management import skill_cleanup as cleanup, skill_preparation as preparation
from app.overseas.management import skill_publication as publication, installed_catalog as catalog
from app.overseas.management.installed_tree import digest
from app.overseas.management.models import Audit
from test_skill_physical_history import history, owned_job, overseas, transfers
from test_overseas_skill_transfers import DOCUMENT, URL, deletion, upload, install
from test_skill_physical_maintenance import pause


def fail_prepare(*args, **kwargs):
    raise OSError('injected preparation failure before pending journal')


def total(h):
    return cleanup.footprint(h.store) + cleanup.allocated(h.root)


def test_history_copy_prejournal_failure_retry_reports_original_net_zero(history, monkeypatch):
    h = history
    job = owned_job(h)
    before = total(h)
    original = publication.prepare_release
    monkeypatch.setattr(publication, 'prepare_release', fail_prepare)
    assert deletion(h.client, h.item, h.package).status_code == 503
    assert (job.owner / 'skill-history').exists()
    assert not (h.store.installed_root / '.pending.json').exists()
    ledger = preparation.load(h.store.installed_root)
    assert ledger['owners'] and preparation.history_bytes(ledger) > 0
    # Retry may refresh availability versions, but must retain the original window.
    monkeypatch.setattr(publication, 'prepare_release', original)
    result = deletion(h.client, h.item, h.package)
    assert result.status_code == 200, result.text
    assert result.json()['reclaimedBytes'] == max(0, before - total(h)) == 0
    assert not (h.store.installed_root / '.preparing.json').exists()
    assert (job.owner / 'skill-history').exists()


def test_central_object_promoted_before_failure_is_not_rebased(history, monkeypatch):
    h = history
    owned_job(h)
    transfer, _ = upload(h.client, {'SKILL.md': DOCUMENT + b'updated', 'assets/new.bin': b'new'})
    before = total(h)
    central_before = cleanup.footprint(h.store)
    original = publication.prepare_release

    def fail_after_promote(*args, **kwargs):
        original(*args, **kwargs)
        raise OSError('injected after central objects promoted')

    monkeypatch.setattr(publication, 'prepare_release', fail_after_promote)
    assert install(h.client, transfer).status_code == 503
    destination = h.store.installed_root / 'packages' / 'folder-test' / transfer['package']['checksum']
    assert destination.exists()
    ledger = preparation.load(h.store.installed_root)
    assert ledger['beforeBytes'] == central_before
    assert not (h.store.installed_root / '.pending.json').exists()
    monkeypatch.setattr(publication, 'prepare_release', original)
    # Same name may abandon a failed update in favour of deletion; both copies count.
    result = deletion(h.client, h.item, h.package)
    assert result.status_code == 200, result.text
    assert not destination.exists()
    assert result.json()['reclaimedBytes'] == max(0, before - total(h))
    with h.factory() as session:
        audit = session.scalar(select(Audit).where(Audit.action == 'skill.delete'))
        assert audit.after['cleanupComplete']


def test_retry_appends_new_owner_baseline_before_copy(history, monkeypatch):
    h = history
    first = owned_job(h)
    original = publication.prepare_release
    monkeypatch.setattr(publication, 'prepare_release', fail_prepare)
    assert deletion(h.client, h.item, h.package).status_code == 503
    baseline = preparation.load(h.store.installed_root)
    second = owned_job(h, kind='analysis')
    monkeypatch.setattr(publication, 'prepare_release', original)
    original_preserve = publication.references.preserve

    def verify_baseline(session, jobs):
        current = preparation.load(h.store.installed_root)
        assert len(current['owners']) == 2
        assert current['beforeBytes'] == baseline['beforeBytes']
        assert not (second.owner / 'skill-history').exists()
        return original_preserve(session, jobs)

    monkeypatch.setattr(publication.references, 'preserve', verify_baseline)
    result = deletion(h.client, h.item, h.package)
    assert result.status_code == 200, result.text
    assert result.json()['reclaimedBytes'] == 0
    assert (first.owner / 'skill-history').exists() and (second.owner / 'skill-history').exists()


@pytest.mark.parametrize('change', ['digest', 'owner', 'metadata', 'negative'])
def test_tampered_preparation_refuses_retry_before_gc(history, monkeypatch, change):
    h = history
    owned_job(h)
    original = publication.prepare_release
    monkeypatch.setattr(publication, 'prepare_release', fail_prepare)
    assert deletion(h.client, h.item, h.package).status_code == 503
    path = h.store.installed_root / '.preparing.json'
    value = json.loads(path.read_text())
    if change == 'digest':
        value['beforeBytes'] += 10000
    else:
        if change == 'owner':
            value['owners'] = {'../outside': 0}
        elif change == 'metadata':
            value['metadata']['studio/../../outside'] = 0
        else:
            value['beforeBytes'] = -1
        value['digest'] = digest({key: item for key, item in value.items() if key != 'digest'})
    path.write_text(json.dumps(value))
    central = h.store.installed_root / 'packages' / 'folder-test' / h.package['checksum']
    monkeypatch.setattr(publication, 'prepare_release', original)
    result = deletion(h.client, h.item, h.package)
    assert result.status_code == 503, result.text
    assert central.exists() and path.exists()


def test_unfinished_preparation_rejects_different_skill_publication(history, monkeypatch):
    h = history
    original = publication.prepare_release
    monkeypatch.setattr(publication, 'prepare_release', fail_prepare)
    assert deletion(h.client, h.item, h.package).status_code == 503
    baseline = (h.store.installed_root / '.preparing.json').read_bytes()
    second, _ = upload(h.client, {'SKILL.md': DOCUMENT.replace(b'folder-test', b'other-test')})
    monkeypatch.setattr(publication, 'prepare_release', original)
    result = install(h.client, second)
    assert result.status_code == 409 and 'folder-test' in result.text
    assert (h.store.installed_root / '.preparing.json').read_bytes() == baseline
    assert not (h.store.installed_root / 'packages' / 'other-test').exists()
    assert deletion(h.client, h.item, h.package).status_code == 200


def test_empty_install_preparation_does_not_need_execution_root(transfers, monkeypatch):
    client, _, _, store = transfers
    transfer, _ = upload(client)
    original = publication.prepare_release
    monkeypatch.setattr(publication, 'prepare_release', fail_prepare)
    assert install(client, transfer).status_code == 503
    assert catalog.read_catalog(store.installed_root) == (None, [])
    monkeypatch.setattr(publication, 'prepare_release', original)
    assert install(client, transfer).status_code == 200
    assert not (store.installed_root / '.preparing.json').exists()


def test_full_maintenance_can_finish_failed_single_name_preparation(history, monkeypatch):
    from app.overseas.management import skill_maintenance as maintenance
    h = history
    owned_job(h)
    before = total(h)
    central_before = cleanup.footprint(h.store)
    original = publication.prepare_release
    monkeypatch.setattr(publication, 'prepare_release', fail_prepare)
    assert deletion(h.client, h.item, h.package).status_code == 503
    pause(h)
    with h.factory() as session, pytest.raises(OSError):
        maintenance.reclaim(h.store, session, h.actor, h.package['release'], False)
    monkeypatch.setattr(publication, 'prepare_release', original)
    with h.factory() as session:
        result = maintenance.reclaim(h.store, session, h.actor, h.package['release'], False)
    assert result['cleanupComplete']
    assert result['centralBytes'] == central_before
    assert result['historyBytes'] > 0
    assert result['reclaimedBytes'] == max(0, before - total(h)) == 0
    assert not (h.store.installed_root / '.preparing.json').exists()


def test_uncommitted_pointer_rollback_keeps_original_history_baseline(history, monkeypatch):
    from app.overseas.management.skill_transfer_schema import SkillDelete
    h = history
    owned_job(h)
    before = total(h)
    body = SkillDelete(release=h.package['release'], checksum=h.package['checksum'], version=h.item['version'])
    with h.factory() as session:
        original = session.commit
        failures = []

        def fail_once():
            if not failures:
                failures.append(True)
                raise OSError('injected commit failure')
            return original()

        monkeypatch.setattr(session, 'commit', fail_once)
        with pytest.raises(OSError, match='commit failure'):
            publication.delete(h.store, session, h.actor, h.item['id'], body)
    assert catalog.read_catalog(h.store.installed_root)[0] == h.package['release']
    assert not (h.store.installed_root / '.pending.json').exists()
    assert preparation.load(h.store.installed_root)['owners']
    result = deletion(h.client, h.item, h.package)
    assert result.status_code == 200, result.text
    assert result.json()['reclaimedBytes'] == max(0, before - total(h)) == 0


def test_linked_preparation_journal_is_rejected(history, monkeypatch, tmp_path):
    h = history
    monkeypatch.setattr(publication, 'prepare_release', fail_prepare)
    assert deletion(h.client, h.item, h.package).status_code == 503
    path = h.store.installed_root / '.preparing.json'
    outside = tmp_path / 'independent.json'
    data = path.read_bytes()
    outside.write_bytes(data)
    path.unlink()
    os.link(outside, path)
    try:
        assert deletion(h.client, h.item, h.package).status_code == 503
        assert outside.read_bytes() == data
        assert catalog.read_catalog(h.store.installed_root)[0] == h.package['release']
    finally:
        path.unlink()


def test_journal_names_inside_real_skill_resources_are_counted(transfers):
    client, _, _, store = transfers
    transfer, files = upload(client, {'SKILL.md': DOCUMENT, '.pending.json': b'a' * 9000,
                                     'assets/.preparing.json': b'b' * 13000})
    assert install(client, transfer).status_code == 200
    root = store.installed_root / 'packages' / 'folder-test' / transfer['package']['checksum']
    paths = [root, *root.rglob('*')]
    expected = sum(path.stat().st_blocks * 512 for path in paths) if os.name == 'posix' else sum(
        len(content) for content in files.values())
    assert cleanup.allocated(root) == expected
    assert cleanup.library_footprint(store) == cleanup.allocated(store.installed_root)
