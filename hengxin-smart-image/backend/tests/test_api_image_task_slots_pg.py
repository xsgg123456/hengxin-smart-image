from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock

import pytest
from sqlalchemy import select

from app.modules.api_image_edits.claims import claim
from app.modules.api_image_edits.execution import execute_batch
from app.modules.api_image_edits.models import ApiItem, ApiTask
from app.modules.api_image_edits.relay import RelayResult
from app.modules.api_image_edits.schemas import CreateTask
from app.modules.api_image_edits.service import submit
from files_helpers import image_bytes
from test_api_image_domain import enabled_api
from test_api_image_execution_pg import pg_api
from test_api_image_parallel_pg import task11

pytestmark = pytest.mark.integration


def six_tasks(factory, user, store):
    first = task11(factory, user, store)
    with factory() as session:
        source_ids = list(session.scalars(select(ApiItem.source_id).where(
            ApiItem.task_id == first).order_by(ApiItem.position)))
    data = CreateTask(name='五任务并发', prompt='p', originalFileIds=source_ids,
                      materialFileId=source_ids[0])
    result = [first]
    for index in range(5):
        with factory() as session:
            result.append(submit(session, user, data, f'other-{index}'))
    return result


def test_racing_deliveries_claim_only_five_tasks_and_fifty_images(pg_api):
    factory, user, _, store = pg_api
    ids = six_tasks(factory, user, store)
    with ThreadPoolExecutor(max_workers=15) as pool:
        values = [value for value in pool.map(lambda _: claim(factory), range(70)) if value]
    assert len(values) == len({value[0] for value in values}) == 50
    with factory() as session:
        for key in ids[:5]:
            items = session.scalars(select(ApiItem).where(ApiItem.task_id == key)
                                    .order_by(ApiItem.position)).all()
            assert all(item.state == 'running' for item in items[:10])
            assert items[10].state == 'queued'
        assert session.get(ApiTask, ids[5]).state == 'queued'


def test_five_executor_batches_overlap_with_fifty_calls(pg_api):
    factory, user, _, store = pg_api
    ids = six_tasks(factory, user, store)
    barrier, lock = Barrier(50), Lock()
    counts = {'active': 0, 'peak': 0}
    class Client:
        def generate(self, *args):
            with lock:
                counts['active'] += 1
                counts['peak'] = max(counts['peak'], counts['active'])
            barrier.wait(timeout=40)
            with lock:
                counts['active'] -= 1
            return RelayResult(image_bytes=image_bytes())
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(lambda _: execute_batch(factory, store, Client()), range(5)))
    assert results == [10] * 5
    assert counts == {'active': 0, 'peak': 50}
    with factory() as session:
        for key in ids[:5]:
            assert session.get(ApiTask, key).state == 'running'  # Batch 2 keeps its slot.
        assert session.get(ApiTask, ids[5]).state == 'queued'
    # The next invocation finishes the second batches, then allows task six.
    reservations = [claim(factory) for _ in range(6)]
    assert all(reservations[:5]) and reservations[5] is None
