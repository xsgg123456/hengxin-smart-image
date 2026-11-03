from uuid import UUID
import pytest
from sqlalchemy import select
from app.overseas.drafts import source
from app.overseas.drafts.models import DraftImport, RequirementDraft
from test_overseas_tasks import overseas, setup, ROOT, HEADERS, add_member, create, payload
from test_overseas_materials import MemoryStore
from app.storage.minio_store import get_store

DRAFT = ROOT + '/requirement-draft'


@pytest.fixture
def drafts(overseas, monkeypatch):
    client, factory, actor, designer = setup(overseas)
    data = {'count': 1, 'list': [{'id': 'req-1', 'title': '灯具', 'designerName': '候选设计', 'files': [
        {'id': 'file-1', 'filename': '图需.PPTX', 'size': 3, 'contentType': 'application/octet-stream',
         'category': 'attachment', 'downloadUrl': '/api/files/file-1/download?token=SECRET'},
        {'id': 'file-2', 'filename': '规格.pdf', 'size': 4, 'contentType': 'application/pdf',
         'category': 'attachment', 'downloadUrl': '/api/files/file-2/download?token=SECRET'}]}]}
    monkeypatch.setattr(source, 'fetch', lambda sku: data)
    store = MemoryStore()
    client.app.dependency_overrides[get_store] = lambda: store
    return client, factory, actor, designer, data, store


def choose(client, *, requirement='req-1', sku='A'):
    draft = client.get(DRAFT).json()
    fields = {**draft['fields'], 'skus': [{'code': sku}]}
    return client.post(DRAFT + '/source', json={'version': draft['version'], 'fields': fields,
        'sku': sku, 'requirementId': requirement}, headers=HEADERS)


def test_empty_fields_restore_and_cas(drafts):
    client, factory, actor, _, _, _ = drafts
    first = client.get(DRAFT).json()
    assert first['fields']['designerId'] == '' and first['fields']['skus'] == [{'code': ''}]
    result = client.put(DRAFT, json={'version': first['version'], 'fields': {'name': '只填名称'}}, headers=HEADERS)
    assert result.status_code == 200, result.text
    saved = result.json()
    assert saved['version'] == first['version'] + 1
    assert client.get(DRAFT).json() == saved
    assert client.put(DRAFT, json={'version': first['version'], 'fields': {}}, headers=HEADERS).status_code == 409
    with factory() as session:
        assert session.scalar(select(RequirementDraft)).fields['name'] == '只填名称'


def test_source_metadata_redacted_and_unique_designer(drafts):
    client, factory, _, designer, _, _ = drafts
    result = client.get(ROOT + '/requirement-source?sku=A')
    assert result.status_code == 200
    assert 'SECRET' not in result.text and 'downloadUrl' not in result.text
    assert result.json()['list'][0]['matchedDesigner']['id'] == str(designer)
    add_member(factory, name='候选设计')
    assert client.get(ROOT + '/requirement-source?sku=A').json()['list'][0]['matchedDesigner'] is None


def test_selection_queues_deduplicates_and_replaces_epoch(drafts):
    client, _, _, _, data, _ = drafts
    data['list'][0]['files'].append(data['list'][0]['files'][0])
    first = choose(client)
    assert first.status_code == 200, first.text
    first = first.json()
    assert len(first['imports']) == 2 and all(row['state'] == 'queued' for row in first['imports'])
    assert {row['kind'] for row in first['imports']} == {'requirement', 'competitor'}
    second = choose(client).json()
    assert second['id'] == first['id'] and [row['id'] for row in second['imports']] == [row['id'] for row in first['imports']]
    data['list'].append({**data['list'][0], 'id': 'req-2'})
    replaced = choose(client, requirement='req-2').json()
    assert replaced['id'] != first['id'] and len(replaced['imports']) == 2
    assert client.delete(DRAFT + '/imports/' + first['imports'][0]['id'], headers=HEADERS).status_code == 404


def test_reject_invalid_oversize_and_no_partial_selection(drafts):
    client, _, _, _, data, _ = drafts
    initial = client.get(DRAFT).json()
    data['list'][0]['files'][1]['size'] = 500_000_001
    assert choose(client).status_code == 422
    assert client.get(DRAFT).json() == initial
    data['list'][0]['files'] = [{**data['list'][0]['files'][0], 'id': str(i)} for i in range(101)]
    assert choose(client).status_code == 422


def test_clear_cancels_jobs_rotates_key_and_version(drafts):
    client, factory, _, _, _, _ = drafts
    draft = choose(client).json()
    cleared = client.request('DELETE', DRAFT, json={'version': draft['version']}, headers=HEADERS)
    assert cleared.status_code == 200
    assert cleared.json()['id'] != draft['id'] and cleared.json()['submitKey'] != draft['submitKey']
    assert cleared.json()['imports'] == [] and cleared.json()['source'] is None
    with factory() as session:
        assert {row.state for row in session.scalars(select(DraftImport))} == {'cancelled'}
    assert client.request('DELETE', DRAFT, json={'version': draft['version']}, headers=HEADERS).status_code == 409


def test_upload_and_atomic_consume_retry(drafts):
    client, _, _, designer, _, _ = drafts
    first = client.get(DRAFT).json()
    fields = {k: v for k, v in payload(designer).items() if k != 'remarks'}
    fields['skus'] = [{'code': 'A'}]
    saved = client.put(DRAFT, json={'version': first['version'], 'fields': fields}, headers=HEADERS).json()
    response = client.post(ROOT + '/materials?kind=competitor&draftId=' + saved['id'],
        files={'file': ('x.csv', b'a,b')}, headers=HEADERS)
    assert response.status_code == 201, response.text
    material = response.json()
    draft = client.get(DRAFT).json()
    assert draft['materials'][0]['id'] == material['id'] and draft['version'] == saved['version']
    body = {**draft['fields'], 'draftId': draft['id'], 'draftVersion': draft['version'], 'materialIds': [material['id']]}
    wrong = create(client, {**body, 'name': '未保存'}, key=draft['submitKey'])
    assert wrong.status_code == 409
    assert client.get(DRAFT).json()['id'] == draft['id']
    created = create(client, body, key=draft['submitKey'])
    assert created.status_code == 201, created.text
    cleared = client.get(DRAFT).json()
    assert cleared['lastSubmittedTaskId'] == created.json()['id'] and cleared['id'] != draft['id']
    assert cleared['lastSubmittedKey'] == draft['submitKey']
    assert create(client, body, key=draft['submitKey']).status_code == 200
    late = client.post(ROOT + '/materials?kind=competitor&draftId=' + draft['id'],
        files={'file': ('late.csv', b'a,b')}, headers=HEADERS)
    assert late.status_code == 409
    # A later draft has its own key; the previous receipt cannot acknowledge it.
    saved = client.put(DRAFT, json={'version': cleared['version'], 'fields': fields}, headers=HEADERS).json()
    assert saved['submitKey'] != saved['lastSubmittedKey']
    body2 = {**saved['fields'], 'draftId': saved['id'], 'draftVersion': saved['version']}
    created2 = create(client, body2, key=saved['submitKey'])
    assert created2.status_code == 201
    final = client.get(DRAFT).json()
    assert final['lastSubmittedKey'] == saved['submitKey']
    assert final['lastSubmittedTaskId'] == created2.json()['id'] != created.json()['id']


def test_other_owner_cannot_modify_or_attach(drafts):
    from app.overseas.drafts import hooks, service
    from app.overseas.auth.models import Member
    client, factory, _, _, _, _ = drafts
    draft = choose(client).json()
    other = add_member(factory)
    with factory() as session:
        user = session.get(Member, other)
        mine = service.owned(session, user)
        assert mine.epoch != UUID(draft['id']) and mine.source is None
        with pytest.raises(Exception) as error:
            service.modify_import(session, user, UUID(draft['imports'][0]['id']))
        assert error.value.status_code == 404


def test_queued_or_failed_import_blocks_create(drafts):
    client, _, _, designer, _, _ = drafts
    draft = choose(client).json()
    fields = {k: v for k, v in payload(designer).items() if k != 'remarks'}
    fields['skus'] = [{'code': 'A'}]
    draft = client.put(DRAFT, json={'version': draft['version'], 'fields': fields}, headers=HEADERS).json()
    result = create(client, {**draft['fields'], 'draftId': draft['id'], 'draftVersion': draft['version']})
    assert result.status_code == 409 and '附件' in result.text


def test_source_io_releases_session_and_late_response_cannot_overwrite(drafts, monkeypatch):
    from app.overseas.drafts import service
    from app.overseas.drafts.selection import select_source
    from app.overseas.drafts.schemas import SaveDraft, SelectSource
    from app.overseas.auth.models import Member
    client, factory, actor, _, data, _ = drafts
    draft = client.get(DRAFT).json()
    with factory() as session:
        user = session.get(Member, actor)
        def fetch(sku):
            assert not session.in_transaction()
            with factory() as other:
                service.save(other, other.get(Member, actor), SaveDraft(version=draft['version'], fields={'name': '新输入'}))
            return data
        monkeypatch.setattr(source, 'fetch', fetch)
        with pytest.raises(Exception) as error:
            select_source(session, user, SelectSource(version=draft['version'], sku='A',
                requirementId='req-1', fields={'skus': [{'code': 'A'}]}))
        assert error.value.status_code == 409
    assert client.get(DRAFT).json()['fields']['name'] == '新输入'


def test_empty_sku_array_and_invalid_owner_upload_are_rejected(drafts):
    client, factory, _, _, _, _ = drafts
    first = client.get(DRAFT).json()
    assert client.put(DRAFT, json={'version': first['version'], 'fields': {'skus': []}}, headers=HEADERS).status_code == 422
    from app.overseas.auth.models import Member
    from app.overseas.drafts import service
    other = add_member(factory)
    with factory() as session:
        foreign = service.finish(session, service.owned(session, session.get(Member, other)))
    response = client.post(ROOT + '/materials?kind=competitor&draftId=' + foreign['id'],
        files={'file': ('foreign.csv', b'abc')}, headers=HEADERS)
    assert response.status_code == 409


def test_revocation_during_query_is_rechecked(drafts, monkeypatch):
    from app.overseas.auth.models import Member
    client, factory, actor, _, data, _ = drafts
    def fetch(sku):
        with factory.begin() as session:
            session.get(Member, actor).status = 'disabled'
        return data
    monkeypatch.setattr(source, 'fetch', fetch)
    assert client.get(ROOT + '/requirement-source?sku=A').status_code == 403
