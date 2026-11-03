"""Multiple originals survive submission, review evidence and historical resubmission."""
from uuid import uuid4

from test_overseas_tasks import overseas, create, payload, ROOT
from test_overseas_materials import materials, upload
from test_overseas_requirements import review
from test_overseas_assignment import change_roles
from test_overseas_plans import post


def test_multiple_each_kind_review_resubmit_and_original_download(materials):
    client, factory, actor, designer, _ = materials
    originals = [upload(client, f'original-{i}'.encode(), name, kind).json() for i, (name, kind) in enumerate([
        ('brief.ppt', 'requirement'), ('brief2.PPTX', 'requirement'),
        ('analysis.csv', 'competitor'), ('reference.pdf', 'competitor')])]
    ids = [item['id'] for item in originals]
    result = create(client, {**payload(designer), 'materialIds': ids})
    assert result.status_code == 201, result.text
    task = result.json()
    assert {x['id'] for x in client.get(ROOT + '/tasks/' + task['id'] + '/materials').json()} == set(ids)
    change_roles(factory, actor, ('super_admin',))
    rejected = review(client, task, 'reject', '补充资料').json()
    assert set(rejected['requirementsReviews'][0]['materialIds']) == set(ids)
    replacement = upload(client, b'new', 'new.csv').json()
    chosen = [*ids[:2], replacement['id']]
    response = post(client, task, '/resubmit', {**payload(designer),
        'materialIds': chosen, 'version': rejected['version']}, 'resubmit-multiple')
    assert response.status_code == 200, response.text
    resubmitted = response.json()
    assert len(resubmitted['skus']) == 2  # Legacy tasks retain all SKUs.
    assert set(resubmitted['requirementsReviews'][0]['materialIds']) == set(ids)
    assert {x['id'] for x in client.get(ROOT + '/tasks/' + task['id'] + '/materials').json()} == set(chosen)
    approved = review(client, resubmitted, key='approve-multiple')
    assert approved.status_code == 200, approved.text
    assert approved.json()['status'] == 'studio'
    for i, item in enumerate(originals):
        assert client.get(ROOT + '/materials/' + item['id'] + '/content').content == f'original-{i}'.encode()


def test_draft_create_requires_single_sku_and_paired_reference(materials):
    client, _, _, designer, _ = materials
    body = payload(designer)
    for extra in ({'draftId': str(uuid4())}, {'draftVersion': 1},
                  {'draftId': str(uuid4()), 'draftVersion': 1}):
        assert create(client, {**body, **extra}).status_code == 422


def test_historical_resubmit_fingerprint_does_not_gain_draft_fields():
    from app.overseas.tasks.schemas import ResubmitTask
    body = {**payload(uuid4()), 'version': 2, 'materialIds': [str(uuid4())]}
    parsed = ResubmitTask(**body).model_dump(mode='json')
    assert set(parsed) == set(body)


def test_upload_storage_has_no_open_database_transaction(materials, monkeypatch):
    from app.overseas.materials import files
    client, _, _, _, store = materials
    original_save, original_put = files.save_upload, store.put

    def save(session, *args):
        def put(record, data):
            assert not session.in_transaction()
            original_put(record, data)
            assert not session.in_transaction()
        monkeypatch.setattr(store, 'put', put)
        return original_save(session, *args)

    monkeypatch.setattr(files, 'save_upload', save)
    assert upload(client).status_code == 201
