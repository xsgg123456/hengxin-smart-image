"""Retry, crash recovery and concurrent publication against real isolated trees."""
import asyncio
import json
import os
from pathlib import Path
from uuid import uuid4
import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from app.overseas.management import installed_catalog as catalog, skill_publication as publication
from app.overseas.management.models import Audit
from app.overseas.management.skill_publisher import create_app
from app.overseas.management.skill_transfer_store import TransferStore, atomic_json
from test_overseas_skill_transfers import transfers, upload, install, manifest, DOCUMENT, URL, HEADERS
from test_overseas_tasks import overseas


def test_upload_mismatch_restart_resume_cancel_and_idempotency(transfers):
    client, _, actor, store = transfers
    body = {'rootName': 'original', 'entries': manifest({'SKILL.md': DOCUMENT})}
    headers = {**HEADERS, 'Idempotency-Key': 'retry-create'}
    response = client.post(URL + '/skill-transfers', headers=headers, json=body)
    state = response.json()
    assert client.post(URL + '/skill-transfers', headers=headers, json=body).json()['id'] == state['id']
    assert client.post(URL + '/skill-transfers', headers=headers, json={**body, 'rootName': 'changed'}).status_code == 409
    path = URL + f"/skill-transfers/{state['id']}"
    bad = client.put(path + '/files', params={'path': 'SKILL.md'}, headers=HEADERS, content=b'wrong')
    assert bad.status_code == 422
    reopened = TransferStore(store.path, store.installed_root)
    assert reopened.load(state['id'], actor)['status'] == 'failed'
    assert client.post(path + '/validate', headers=HEADERS).status_code == 422
    assert client.put(path + '/files', params={'path': '../SKILL.md'}, headers=HEADERS, content=DOCUMENT).status_code == 422
    assert client.put(path + '/files', params={'path': 'SKILL.md'}, headers=HEADERS, content=DOCUMENT + b'overflow').status_code == 413
    assert client.put(path + '/files', params={'path': 'SKILL.md'}, headers=HEADERS, content=DOCUMENT).status_code == 200
    assert client.post(path + '/validate', headers=HEADERS).status_code == 200
    assert client.delete(path, headers=HEADERS).status_code == 200
    assert client.delete(path, headers=HEADERS).status_code == 200
    assert client.post(path + '/validate', headers=HEADERS).status_code == 409


def test_copy_failure_first_install_leaves_valid_empty_catalog(transfers, monkeypatch):
    client, _, _, store = transfers
    transfer, _ = upload(client)
    original = publication.catalog.verify_package
    def fail(directory, *args, **kwargs):
        if directory.name.startswith('.install-'):
            raise ValueError('injected copy failure')
        return original(directory, *args, **kwargs)
    monkeypatch.setattr(publication.catalog, 'verify_package', fail)
    assert install(client, transfer).status_code == 503
    assert catalog.read_catalog(store.installed_root)[1] == []
    assert client.get(URL + '/skills').status_code == 200


def test_pointer_failure_keeps_original_and_retry_succeeds(transfers, monkeypatch):
    client, _, _, store = transfers
    first, _ = upload(client)
    assert install(client, first).status_code == 200
    before = catalog.read_catalog(store.installed_root)
    second, _ = upload(client, {'SKILL.md': DOCUMENT + b'new'})
    original, failures = os.replace, []
    def fail_once(source, target):
        if Path(target).name == 'current.json' and not failures:
            failures.append(True)
            raise OSError('injected pointer failure')
        return original(source, target)
    monkeypatch.setattr(os, 'replace', fail_once)
    assert install(client, second).status_code == 503
    assert catalog.read_catalog(store.installed_root) == before
    assert not (store.installed_root / '.pending.json').exists()
    assert install(client, second).status_code == 200


def test_completed_publication_with_lost_state_save_is_replayable(transfers, monkeypatch):
    client, factory, _, store = transfers
    transfer, _ = upload(client)
    original, failures = store.save, []
    def fail_once(state):
        if state['status'] == 'installed' and not failures:
            failures.append(True)
            raise OSError('injected state failure')
        return original(state)
    monkeypatch.setattr(store, 'save', fail_once)
    assert install(client, transfer).status_code == 503
    assert store.load(transfer['id'])['status'] == 'failed'
    recovered = client.get(URL + '/skill-transfers/' + transfer['id'])
    assert recovered.json()['status'] == 'installed'
    response = install(client, transfer)
    assert response.status_code == 200 and response.json()['status'] == 'installed'
    with factory() as session:
        assert len(list(session.scalars(select(Audit).where(Audit.action == 'skill.install')))) == 1


def test_pending_journal_blocks_new_reads_preserves_frozen_and_recovers(transfers):
    client, factory, _, store = transfers
    first, _ = upload(client)
    assert install(client, first).status_code == 200
    item = client.get(URL + '/skills').json()['items'][0]
    frozen = catalog.freeze(item['id'])
    second, _ = upload(client, {'SKILL.md': DOCUMENT + b'new'})
    assert install(client, second).status_code == 200
    newest, _ = catalog.read_catalog(store.installed_root)
    atomic_json(store.installed_root / '.pending.json', {'audit': str(uuid4()),
        'before': frozen['installedRelease'], 'after': newest})
    assert client.get(URL + '/skills').status_code == 503
    assert catalog.frozen_package(frozen).files['SKILL.md'] == DOCUMENT
    with factory() as session:
        publication.recover(store, session)
    assert catalog.read_catalog(store.installed_root)[0] == frozen['installedRelease']
    with factory() as session:
        committed = session.scalar(select(Audit).where(Audit.action == 'skill.update'))
        atomic_json(store.installed_root / '.pending.json', {'audit': str(committed.id),
            'before': frozen['installedRelease'], 'after': newest})
        publication.recover(store, session)
    assert catalog.read_catalog(store.installed_root)[0] == newest


def test_db_commit_failure_rolls_back_pointer_and_availability(transfers, monkeypatch):
    client, factory, actor, store = transfers
    first, _ = upload(client)
    assert install(client, first).status_code == 200
    before = catalog.read_catalog(store.installed_root)
    second, _ = upload(client, {'SKILL.md': DOCUMENT + b'new'})
    with factory() as session:
        original, failures = session.commit, []
        def fail_once():
            if not failures:
                failures.append(True)
                raise OSError('injected DB commit failure')
            return original()
        monkeypatch.setattr(session, 'commit', fail_once)
        with pytest.raises(OSError, match='DB commit'):
            publication.install(store, session, actor, second['id'], second['baseRelease'])
    assert catalog.read_catalog(store.installed_root) == before
    assert install(client, second).status_code == 200


def test_concurrent_distinct_publications_serialize_and_revalidate(transfers):
    client, factory, actor, store = transfers
    first, _ = upload(client)
    second, _ = upload(client, {'SKILL.md': DOCUMENT.replace(b'folder-test', b'other-skill')})
    app = create_app(store, factory)
    async def race():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://publisher') as remote:
            return await asyncio.gather(*[remote.post('/transfers/' + item['id'] + '/install',
                headers={'X-Actor-Id': str(actor)}, json={'baseRelease': item['baseRelease']}) for item in (first, second)])
    responses = asyncio.run(race())
    assert sorted(response.status_code for response in responses) == [200, 409]
    failed = (first, second)[next(i for i, response in enumerate(responses) if response.status_code == 409)]
    refreshed = client.post(URL + '/skill-transfers/' + failed['id'] + '/validate', headers=HEADERS).json()
    assert install(client, refreshed).status_code == 200
    assert len(client.get(URL + '/skills').json()['items']) == 2


@pytest.mark.parametrize('reference', ['assets/missing.png', 'agents/missing.yaml', 'docs/missing.md',
                                     'missing.txt', '../escape.md'])
def test_tampered_staging_and_missing_references_rejected(transfers, reference):
    client, _, _, store = transfers
    transfer, _ = upload(client)
    (store.directory(transfer['id']) / 'package/SKILL.md').write_bytes(DOCUMENT + b'tampered')
    assert install(client, transfer).status_code == 422
    assert catalog.read_catalog(store.installed_root)[1] == []
    files = {'SKILL.md': DOCUMENT + ('[missing](' + reference + ')').encode()}
    state = client.post(URL + '/skill-transfers', headers=HEADERS,
        json={'rootName': 'missing', 'entries': manifest(files)}).json()
    path = URL + '/skill-transfers/' + state['id']
    client.put(path + '/files', params={'path': 'SKILL.md'}, headers=HEADERS, content=files['SKILL.md'])
    assert client.post(path + '/validate', headers=HEADERS).status_code == 422


def test_markdown_reference_parser_checks_nested_encoded_and_reference_links():
    from app.overseas.management.skill_transfer_store import validate_references
    files = {'docs/guide.md': b'[ok](../agents/a%20b.yaml#section)\n[doc][ref]\n\n'
             b'[ref]: ../agents/a%20b.yaml "Title"\n\n```md\n[fake](missing.txt)\n```\n'
             b'[external](https://example.test/missing)\n[anchor](#ok)\n[dir](../agents/)'}
    entries = {'docs/guide.md': {}, 'agents/': {'directory': True}, 'agents/a b.yaml': {}}
    validate_references(files, entries)
    for content in (b'[missing][ref]\n\n[ref]: ../docs/missing.md', b'![missing](missing.png)'):
        with pytest.raises(ValueError, match='missing'):
            validate_references({'docs/guide.md': content}, entries)


@pytest.mark.parametrize('body', [b'[Assets](assets/)',
    b'```md\n[example](assets/not-present.png)\n```',
    b'[Assets][ref]\n\n[ref]: assets/ "Empty directory"'])
def test_valid_directory_and_code_examples_survive_install_and_catalog_read(transfers, body):
    client, _, _, store = transfers
    transfer, files = upload(client, {'SKILL.md': DOCUMENT + body})
    assert install(client, transfer).status_code == 200
    item = client.get(URL + '/skills').json()['items'][0]
    descriptor = client.get(URL + '/skills/' + item['id'] + '/package')
    assert descriptor.status_code == 200
    assert descriptor.json()['entries']['assets/'] == {'directory': True}
    assert catalog.read_catalog(store.installed_root)[1][0]['name'] == item['name']


def test_uploaded_links_are_rejected_before_publication(transfers):
    client, _, _, store = transfers
    transfer, _ = upload(client)
    package = store.directory(transfer['id']) / 'package'
    os.link(package / 'SKILL.md', package / 'linked.md')
    assert install(client, transfer).status_code == 422
    assert client.get(URL + '/skills').json()['items'] == []


def test_fixed_download_rejects_missing_path_and_modified_bytes(transfers):
    client, _, _, store = transfers
    transfer, _ = upload(client)
    assert install(client, transfer).status_code == 200
    item = client.get(URL + '/skills').json()['items'][0]
    package = client.get(URL + '/skills/' + item['id'] + '/package').json()
    url = URL + '/skills/' + item['id'] + '/files'
    assert client.get(url, params={'release': package['release'], 'path': '../SKILL.md'}).status_code == 404
    assert client.get(url, params={'release': package['release'], 'path': 'empty/'}).status_code == 404
    asset = store.installed_root / 'releases' / package['release'] / 'folder-test/assets/data.bin'
    asset.write_bytes(b'tampered')
    assert client.get(url, params={'release': package['release'], 'path': 'assets/data.bin'}).status_code == 503
