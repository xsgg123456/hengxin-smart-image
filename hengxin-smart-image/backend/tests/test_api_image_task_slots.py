from datetime import timedelta
from uuid import UUID

from sqlalchemy import select

from app.models import utcnow
from app.modules.api_image_edits.claims import claim
from app.modules.api_image_edits.execution import execute_next
from app.modules.api_image_edits.models import ApiItem, ApiTask
from app.modules.api_image_edits.outcomes import failure
from files_helpers import files_env
from test_api_image_domain import ROOT, create, enabled_api
from test_api_image_execution import Client


def test_five_tasks_sixth_queues_and_failure_releases_slot(files_env):
    web, factory, _, _ = files_env
    ids = [UUID(create(web, 1)[0]) for _ in range(6)]
    reservations = [claim(factory) for _ in range(5)]
    assert all(reservations) and claim(factory) is None
    with factory() as session:
        assert {session.get(ApiItem, r[0]).task_id for r in reservations} == set(ids[:5])
        assert session.get(ApiTask, ids[5]).state == 'queued'
    # Backoff still owns a task slot even though no image lease is live.
    failure(factory, *reservations[0][:2], 'retryable', 'HTTP_503')
    with factory.begin() as session:
        session.get(ApiItem, reservations[0][0]).next_attempt_at = utcnow() + timedelta(hours=1)
    assert claim(factory) is None
    # Definitive failure finishes the task and admits the next queued task.
    failure(factory, *reservations[1][:2], 'permanent', 'INVALID_INPUT')
    sixth = claim(factory)
    assert sixth
    with factory() as session:
        assert session.get(ApiItem, sixth[0]).task_id == ids[5]


def test_finished_revision_and_manual_retry_queue_behind_five_tasks(files_env):
    web, factory, store, _ = files_env
    old, _ = create(web, 1)
    assert execute_next(factory, store, Client())
    failed, _ = create(web, 1)
    reservation = claim(factory)
    failure(factory, *reservation[:2], 'permanent', 'INVALID_INPUT')
    ids = [create(web, 1)[0] for _ in range(5)]
    assert all(claim(factory) for _ in range(5))
    item = web.get(f'{ROOT}/tasks/{old}').json()['items'][0]
    assert web.post(f"{ROOT}/tasks/{old}/items/{item['id']}/revise",
                    json={'baseVersion': 1, 'text': '调整'},
                    headers={'Idempotency-Key': 'revise-old'}).status_code == 202
    assert web.post(f'{ROOT}/tasks/{failed}/retry',
                    headers={'Idempotency-Key': 'retry-old'}).status_code == 202
    assert claim(factory) is None
    with factory() as session:
        assert session.get(ApiTask, UUID(old)).state == 'queued'
        assert session.get(ApiTask, UUID(failed)).state == 'queued'
        assert all(session.get(ApiTask, UUID(key)).state == 'running' for key in ids)


def test_success_releases_slot_and_queued_delete_skips_task(files_env):
    web, factory, store, _ = files_env
    ids = [create(web, 1)[0] for _ in range(7)]
    held = [claim(factory) for _ in range(4)]
    assert all(held)
    assert web.delete(f'{ROOT}/tasks/{ids[5]}').status_code == 200
    assert execute_next(factory, store, Client())  # Fifth task succeeds.
    last = claim(factory)
    with factory() as session:
        assert session.get(ApiItem, last[0]).task_id == UUID(ids[6])
