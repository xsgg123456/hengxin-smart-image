from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.execution.fixture_runner import run_generation
from app.models import utcnow
from app.modules.tasks.models import ImageVersion, RoundRecord
from app.resource_models import FileRecord, UserRecord
from files_helpers import files_env  # noqa: F401
from test_files import upload
from test_revisions import ready, revise, detail, change_state
from test_tasks import task_env, job_for, body, submit  # noqa: F401


def test_historical_base_appends_v3_and_keeps_other_slot(task_env):
    receipt = ready(task_env, 'wallpaper')
    first = detail(task_env, receipt)
    base = first['slots'][1]['versions'][0]['id']
    second = revise(task_env, receipt, target=1, baseVersionId=base).json()
    run_generation(job_for(task_env[1], second), task_env[1], task_env[2])
    before = detail(task_env, receipt)
    screenshot = upload(task_env[0]).json()
    response = revise(task_env, receipt, key='historical', target=1, baseVersionId=base,
                      annotationFileId=screenshot['fileId'])
    assert response.status_code == 202, response.text
    assert revise(task_env, receipt, key='historical', target=1, baseVersionId=base,
                  annotationFileId=screenshot['fileId']).json() == response.json()
    assert revise(task_env, receipt, key='historical', target=1,
                  baseVersionId=before['slots'][1]['currentVersionId']).status_code == 409
    during = detail(task_env, receipt)['rounds'][-1]
    assert during['baseVersionId'] == base and during['baseVersion'] == 1
    assert during['annotation'] == screenshot
    run_generation(job_for(task_env[1], response.json()), task_env[1], task_env[2])
    after = detail(task_env, receipt)
    assert after['slots'][0] == before['slots'][0]
    assert after['slots'][1]['versions'][:2] == before['slots'][1]['versions']
    assert [v['version'] for v in after['slots'][1]['versions']] == [1, 2, 3]


def test_base_validation_and_legacy_client_freezes_current(task_env):
    receipt = ready(task_env, 'wallpaper')
    slots = detail(task_env, receipt)['slots']
    for changes in [dict(baseVersionId=str(uuid4())), dict(baseVersionId='bad'),
                    dict(baseVersionId=slots[1]['currentVersionId']), dict(baseVersionId=None)]:
        assert revise(task_env, receipt, target=0, **changes).status_code == 422
    other = submit(task_env, body(task_env), key='other-task').json()
    run_generation(job_for(task_env[1], other), task_env[1], task_env[2])
    assert revise(task_env, receipt, target=0,
        baseVersionId=detail(task_env, other)['slots'][0]['currentVersionId']).status_code == 422
    response = revise(task_env, receipt, target=0)
    assert response.status_code == 202
    assert detail(task_env, receipt)['rounds'][-1]['baseVersionId'] == slots[0]['currentVersionId']


@pytest.mark.parametrize('property,value', [('status', 'staging'), ('status', 'failed'),
    ('deleted_at', 'now'), ('content_type', 'text/plain'), ('size_bytes', 0),
    ('size_bytes', 10 * 1024**2 + 1)])
def test_invalid_annotation_rejected(task_env, property, value):
    receipt = ready(task_env)
    image = upload(task_env[0]).json()
    with task_env[1].begin() as session:
        setattr(session.get(FileRecord, UUID(image['fileId'])), property,
                utcnow() if value == 'now' else value)
    assert revise(task_env, receipt, target=0, annotationFileId=image['fileId']).status_code == 422


def test_annotation_upload_owner_and_cross_actor_frozen_retry(task_env):
    receipt = ready(task_env)
    image = upload(task_env[0]).json()
    accepted = revise(task_env, receipt, target=0, annotationFileId=image['fileId']).json()
    change_state(task_env, accepted, 'failed')
    original = detail(task_env, receipt)['rounds'][-1]
    with task_env[1].begin() as session:
        user = UserRecord(id=uuid4(), name='其他操作者', role='operator', status='active',
                          identity_source='development')
        session.add(user)
        task_env[3][0] = user.id
    assert revise(task_env, receipt, key='foreign', target=0,
                  annotationFileId=image['fileId']).status_code == 403
    args = dict(target=0, retry=True, sourceRoundId=accepted['roundId'])
    assert revise(task_env, receipt, key='retry', **args, annotationFileId=None).status_code == 409
    assert revise(task_env, receipt, key='retry', **args, baseVersionId=None).status_code == 409
    response = revise(task_env, receipt, key='retry', **args)
    assert response.status_code == 202, response.text
    retried = detail(task_env, receipt)['rounds'][-1]
    for field in ('baseVersionId', 'baseVersion', 'annotation', 'note', 'target'):
        assert retried[field] == original[field]
    assert task_env[0].get(image['url']).status_code == 200
    assert task_env[0].get('/api/v1/files/' + image['fileId']).status_code == 200
    task_env[3][0] = None
    assert task_env[0].get(image['url']).status_code == 401


def test_whole_set_rejects_single_inputs_and_missing_annotation(task_env):
    receipt = ready(task_env)
    base = detail(task_env, receipt)['slots'][0]['currentVersionId']
    assert revise(task_env, receipt, baseVersionId=base).status_code == 422
    assert revise(task_env, receipt, annotationFileId=str(uuid4())).status_code == 422
    assert revise(task_env, receipt, target=0, annotationFileId=str(uuid4())).status_code == 422
    assert revise(task_env, receipt, target=0, annotationFileId='bad').status_code == 422


def test_base_file_unavailable_and_stricter_upload_limit(task_env, monkeypatch):
    receipt = ready(task_env)
    base = detail(task_env, receipt)['slots'][0]['currentVersionId']
    image = upload(task_env[0]).json()
    monkeypatch.setattr('app.modules.tasks.revision_inputs.values', lambda s: {'maxUploadBytes': 1})
    assert revise(task_env, receipt, target=0, annotationFileId=image['fileId']).status_code == 422
    with task_env[1].begin() as session:
        version = session.get(ImageVersion, UUID(base))
        session.get(FileRecord, version.file_id).deleted_at = utcnow()
    assert revise(task_env, receipt, target=0, baseVersionId=base).status_code == 422


def test_task_delete_preserves_round_annotation_reference(task_env):
    receipt = ready(task_env)
    image = upload(task_env[0]).json()
    response = revise(task_env, receipt, target=0, annotationFileId=image['fileId']).json()
    run_generation(job_for(task_env[1], response), task_env[1], task_env[2])
    assert task_env[0].delete('/api/v1/tasks/' + receipt['taskId']).status_code == 200
    with task_env[1]() as session:
        assert session.get(RoundRecord, UUID(response['roundId'])).annotation_file_id == UUID(image['fileId'])
        assert session.get(FileRecord, UUID(image['fileId'])).status == 'ready'
    assert task_env[0].get(image['url']).status_code == 200


def test_explicit_no_result_base_and_retry_keep_null(task_env):
    receipt = submit(task_env).json()
    change_state(task_env, receipt, 'failed')
    response = revise(task_env, receipt, target=0, baseVersionId=None)
    assert response.status_code == 202, response.text
    accepted = response.json()
    change_state(task_env, accepted, 'failed')
    retried = revise(task_env, receipt, key='retry-null', target=0, retry=True,
                     sourceRoundId=accepted['roundId']).json()
    with task_env[1]() as session:
        round = session.get(RoundRecord, UUID(retried['roundId']))
        assert round.base_version_id is None
        assert round.execution_config['singleInputFrozen'] is True


def test_new_optional_fields_preserve_legacy_idempotency_hash():
    import hashlib
    import json
    from app.contracts.business import RevisionInput
    from app.modules.tasks.idempotency import fingerprint
    data = dict(taskId=str(uuid4()), target=0, note='修改')
    old_hash = hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False,
        separators=(',', ':')).encode()).hexdigest()
    assert fingerprint(RevisionInput(**data)) == old_hash
    assert fingerprint(RevisionInput(**data, baseVersionId=None)) != old_hash
