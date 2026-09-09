from uuid import UUID, uuid4
import pytest
from sqlalchemy import select
from files_helpers import files_env
from test_tasks import task_env, body, submit, job_for
from app.execution.fixture_runner import run_generation
from app.models import Job, Outbox
from app.modules.tasks.claims import claim
from app.modules.tasks.models import ImageVersion, ResultSlotRecord, RoundRecord
from app.modules.tasks.results import publish_results


def test_template_edit_and_delete_preserve_accepted_snapshot(task_env):
    client, factory, store, _ = task_env
    data = body(task_env, 'wallpaper')
    receipt = submit(task_env, data).json()
    path = '/api/v1/tasks/' + receipt['taskId']
    frozen = client.get(path).json()['task']['templateSnapshot']
    template_path = '/api/v1/templates/' + data['templateId']
    changed = client.put(template_path, json={
        'name': '已改名模板', 'mode': 'wallpaper', 'images': data['sources'],
        'skillVersionId': data['skillVersionId'], 'active': True,
        'notes': '新说明', 'expectedVersion': 1,
    })
    assert changed.status_code == 200, changed.text
    assert changed.json()['version'] == 2
    assert client.delete(template_path).status_code == 204
    assert client.get(template_path).status_code == 404
    assert submit(task_env, data).json() == receipt
    run_generation(job_for(factory, receipt), factory, store)
    result = client.get(path).json()
    assert result['task']['templateSnapshot'] == frozen
    assert result['task']['templateVersion'] == 1
    assert result['task']['outputCount'] == len(result['slots']) == 2
    assert len(result['task']['images']) == 2


def test_invalid_second_output_rolls_back_first_version_and_current_pointer(task_env):
    _, factory, _, _ = task_env
    data = body(task_env, 'wallpaper')
    receipt = submit(task_env, data).json()
    job_id = job_for(factory, receipt)
    token = claim(factory, job_id)
    with pytest.raises(ValueError, match='Output file is not readable'):
        publish_results(factory, job_id, token, [UUID(data['sources'][0]['fileId']), uuid4()])
    with factory() as session:
        assert session.scalar(select(ImageVersion)) is None
        slots = session.scalars(select(ResultSlotRecord)).all()
        assert len(slots) == 2 and all(slot.current_version_id is None for slot in slots)
        assert session.get(Job, job_id).status == 'running'
        assert session.get(RoundRecord, UUID(receipt['roundId'])).status == 'running'
        assert session.get(Outbox, job_id).completed_at is None
