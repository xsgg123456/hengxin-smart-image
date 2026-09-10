import json
from uuid import UUID

import pytest
from sqlalchemy import select

from app.execution.output_collector import collect_outputs, OutputCollectionError
from app.modules.tasks.claims import claim
from app.modules.tasks.models import ImageVersion, RoundRecord, ResultSlotRecord
from app.modules.tasks.results import publish_results
from app.modules.tasks.service import accept_round
from app.contracts.business import RevisionInput
from app.resource_models import UserRecord
from files_helpers import files_env, image_bytes  # noqa: F401
from test_tasks import task_env, body, submit, job_for  # noqa: F401
from app.execution.fixture_runner import run_generation


def test_explicit_partial_manifest_preserves_slot_positions(tmp_path):
    root = tmp_path / 'generated_images/session-a'
    root.mkdir(parents=True)
    (root / 'exec-new.png').write_bytes(image_bytes())
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps({'outputs': [
        {'slot': 1, 'error': '工具失败'}, {'slot': 0, 'file': 'exec-new.png'}]}))
    images = collect_outputs(tmp_path, 'session-a', {}, 2, manifest, allow_partial=True)
    assert images[0].name == 'exec-new.png' and images[1] is None
    with pytest.raises(OutputCollectionError):
        collect_outputs(tmp_path, 'session-a', {}, 2, manifest)
    # A declared failure cannot hide another unaccounted-for generated file.
    (root / 'unmapped.png').write_bytes(image_bytes())
    with pytest.raises(OutputCollectionError):
        collect_outputs(tmp_path, 'session-a', {}, 2, manifest, allow_partial=True)


def test_all_failure_requires_explicit_complete_manifest(tmp_path):
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps({'outputs': [{'slot': 0, 'error': '失败'}]}))
    assert collect_outputs(tmp_path, 'session-a', {}, 1, manifest, allow_partial=True) == [None]
    manifest.write_text(json.dumps({'outputs': [{'slot': 0, 'error': '失败', 'file': 'x.png'}]}))
    with pytest.raises(OutputCollectionError):
        collect_outputs(tmp_path, 'session-a', {}, 1, manifest, allow_partial=True)


@pytest.mark.parametrize('successful', [True, False])
def test_partial_and_failed_rounds_preserve_old_versions(task_env, successful):
    client, factory, store, identity = task_env
    created = submit(task_env, body(task_env, 'wallpaper')).json()
    run_generation(job_for(factory, created), factory, store)
    before = client.get('/api/v1/tasks/' + created['taskId']).json()
    with factory() as session:
        user = session.get(UserRecord, identity[0])
        receipt = accept_round(session, user, UUID(created['taskId']), RevisionInput(
            taskId=created['taskId'], target=None, note='整套更新'), 'partial-test')
    job_id = job_for(factory, receipt.model_dump())
    token = claim(factory, job_id)
    first = before['slots'][0]['versions'][0]['fileId']
    assert publish_results(factory, job_id, token, [UUID(first) if successful else None, None])
    after = client.get('/api/v1/tasks/' + created['taskId']).json()
    assert after['task']['state'] == ('部分失败' if successful else '失败')
    assert after['slots'][1]['currentVersionId'] == before['slots'][1]['currentVersionId']
    assert after['slots'][1]['versions'] == before['slots'][1]['versions']
    assert after['slots'][1]['error']
    assert len(after['slots'][0]['versions']) == (2 if successful else 1)
    assert not publish_results(factory, job_id, token, [UUID(first), UUID(first)])
    with factory() as session:
        assert session.get(RoundRecord, UUID(receipt.roundId)).status == ('partial' if successful else 'failed')


def test_single_success_keeps_incomplete_set_in_partial_lists_until_all_slots_fixed(task_env):
    client, factory, _, identity = task_env
    source = body(task_env, 'wallpaper')
    created = submit(task_env, source).json()
    first_job = job_for(factory, created)
    token = claim(factory, first_job)
    file_id = UUID(source['sources'][0]['fileId'])
    publish_results(factory, first_job, token, [file_id, None])
    for slot in (0, 1):
        with factory() as session:
            receipt = accept_round(session, session.get(UserRecord, identity[0]), UUID(created['taskId']),
                RevisionInput(taskId=created['taskId'], target=slot, note='单张修正'), 'repair-' + str(slot))
        job = job_for(factory, receipt.model_dump())
        assert publish_results(factory, job, claim(factory, job), [file_id])
        detail = client.get('/api/v1/tasks/' + created['taskId']).json()
        assert detail['rounds'][-1]['state'] == '待查看'
        expected = '部分失败' if slot == 0 else '待查看'
        assert detail['task']['state'] == expected
        assert detail['task']['progress'] == (None if slot == 0 else 100)
        for state, count in [('部分失败', 1 if slot == 0 else 0),
                             ('error', 1 if slot == 0 else 0), ('待查看', 0 if slot == 0 else 1)]:
            listing = client.get('/api/v1/tasks', params={'state': state}).json()
            assert listing['total'] == count
            assert listing['stats']['ready'] == (0 if slot == 0 else 1)
