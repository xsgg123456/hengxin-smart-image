from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from threading import Barrier, Lock
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.modules.api_image_edits.claims import claim
from app.modules.api_image_edits.execution import execute_batch
from app.modules.api_image_edits.files import save_upload
from app.modules.api_image_edits.models import ApiItem, ApiTask
from app.modules.api_image_edits.relay import RelayResult
from app.modules.api_image_edits.schemas import CreateTask
from app.modules.api_image_edits.service import submit
from app.modules.api_image_edits.versions import revise
from app.modules.api_image_edits.schemas import ReviseItem
from app.modules.files.validation import validate_image
from files_helpers import image_bytes
from test_api_image_domain import enabled_api
from test_api_image_execution_pg import pg_api

pytestmark = pytest.mark.integration


def task11(factory, user, store):
    with factory() as session:
        originals = []
        for index in range(11):
            image = validate_image(SimpleNamespace(file=BytesIO(image_bytes()),
                filename=f'{index}.png', content_type='image/png'))
            originals.append(save_upload(session, store, user, image).id)
        data = CreateTask(name='11图并发', prompt='p', originalFileIds=originals,
                          materialFileId=originals[0])
        return submit(session, user, data, 'eleven')


def test_concurrent_claimers_reserve_exactly_ten_unique_items(pg_api):
    factory, user, _, store = pg_api
    task_id = task11(factory, user, store)
    barrier = Barrier(16)
    def run(_):
        barrier.wait(timeout=20)
        return claim(factory)
    with ThreadPoolExecutor(max_workers=16) as pool:
        claims = [value for value in pool.map(run, range(16)) if value]
    assert len(claims) == len({value[0] for value in claims}) == 10
    with factory() as session:
        items = session.scalars(select(ApiItem).where(ApiItem.task_id == task_id)
                                .order_by(ApiItem.position)).all()
        assert all(item.state == 'running' for item in items[:10])
        assert items[10].state == 'queued'


def test_ten_real_calls_overlap_then_eleventh_next_batch(pg_api):
    factory, user, _, store = pg_api
    task_id = task11(factory, user, store)
    barrier, lock = Barrier(10), Lock()
    counts = {'active': 0, 'peak': 0, 'calls': 0}
    class ParallelClient:
        def generate(self, *args):
            with lock:
                counts['calls'] += 1
                counts['active'] += 1
                counts['peak'] = max(counts['peak'], counts['active'])
                first = counts['calls'] <= 10
            if first:
                barrier.wait(timeout=20)
            with lock:
                counts['active'] -= 1
            return RelayResult(image_bytes=image_bytes())
    assert execute_batch(factory, store, ParallelClient()) == 10
    assert counts == {'active': 0, 'peak': 10, 'calls': 10}
    with factory() as session:
        items = session.scalars(select(ApiItem).where(ApiItem.task_id == task_id)
                                .order_by(ApiItem.position)).all()
        assert all(item.state == 'succeeded' for item in items[:10])
        assert items[10].state == 'queued'
    assert execute_batch(factory, store, ParallelClient()) == 1
    assert counts['calls'] == 11
    with factory() as session:
        assert session.get(ApiTask, task_id).state == 'succeeded'


def test_earlier_revision_waits_for_later_inflight_batch(pg_api):
    factory, user, _, store = pg_api
    task_id = task11(factory, user, store)
    class Client:
        def generate(self, *args):
            return RelayResult(image_bytes=image_bytes())
    assert execute_batch(factory, store, Client()) == 10
    eleventh = claim(factory)
    assert eleventh
    with factory() as session:
        first = session.scalar(select(ApiItem).where(ApiItem.task_id == task_id, ApiItem.position == 1))
        revise(session, user, task_id, first.id, ReviseItem(baseVersion=1, text='edit'), 'earlier')
    assert claim(factory) is None  # No earlier batch revision while batch 2 is in flight.
    with factory() as session:
        assert session.get(ApiTask, task_id).state == 'running'


def test_old_task_revision_cannot_take_capacity_from_new_inflight_task(pg_api):
    factory, user, data, store = pg_api
    with factory() as session:
        old_task = submit(session, user, data, 'old')
    class Client:
        def generate(self, *args):
            return RelayResult(image_bytes=image_bytes())
    assert execute_batch(factory, store, Client()) == 1
    task11(factory, user, store)
    reservations = [claim(factory) for _ in range(10)]
    assert all(reservations)
    with factory() as session:
        item = session.scalar(select(ApiItem).where(ApiItem.task_id == old_task))
        revise(session, user, old_task, item.id, ReviseItem(baseVersion=1, text='edit'), 'old-edit')
    assert claim(factory) is None
