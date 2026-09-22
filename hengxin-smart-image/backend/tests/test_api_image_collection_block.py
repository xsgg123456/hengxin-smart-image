from datetime import datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select

from app.models import utcnow
from app.modules.api_image_edits.claims import claim
from app.modules.api_image_edits.execution import execute_next
from app.modules.api_image_edits.models import ApiChannel, ApiItem
from files_helpers import files_env, image_bytes
from test_api_image_domain import ROOT, create, enabled_api
from test_api_image_execution import Client, due


def pending_collection(web, factory):
    task_id, _ = create(web, 3)
    items = web.get(ROOT + '/tasks/' + task_id).json()['items']
    with factory.begin() as session:
        first = session.get(ApiItem, UUID(items[0]['id']))
        first.state, first.result_url = 'failed', 'https://example.test/result.png'
        session.get(ApiItem, UUID(items[1]['id'])).state = 'uncertain'
    response = web.post(f"{ROOT}/tasks/{task_id}/items/{items[0]['id']}/retry",
                        headers={'Idempotency-Key': str(uuid4())})
    assert response.status_code == 202
    return task_id, items


def test_manual_collection_retry_bypasses_uncertain_without_regeneration(files_env):
    web, factory, store, _ = files_env
    task_id, _ = pending_collection(web, factory)
    client, downloads = Client(), []
    def download(url):
        downloads.append(url)
        return image_bytes()
    assert execute_next(factory, store, client, download)
    task = web.get(ROOT + '/tasks/' + task_id).json()
    assert [i['state'] for i in task['items']] == ['succeeded', 'uncertain', 'queued']
    assert len(task['items'][0]['versions']) == 1
    assert task['status'] == 'uncertain'
    assert downloads == ['https://example.test/result.png'] and not client.calls
    assert claim(factory) is None


def test_collection_backoff_runs_and_exhausts_while_generation_blocked(files_env):
    web, factory, store, _ = files_env
    task_id, _ = pending_collection(web, factory)
    client, downloads = Client(), []
    def download(url):
        downloads.append(url)
        raise OSError('temporary download failure')
    for index in range(4):
        before = utcnow()
        assert execute_next(factory, store, client, download)
        first = web.get(ROOT + '/tasks/' + task_id).json()['items'][0]
        assert first['state'] == ('collecting' if index < 3 else 'failed')
        if index < 3:
            delay = (datetime.fromisoformat(first['nextAttemptAt']) - before).total_seconds()
            assert 2 ** index <= delay < 2 ** index + 2
            assert claim(factory) is None
        due(factory)
    assert len(downloads) == 4 and not client.calls


def test_blocked_collection_requires_result_and_honors_pause_and_live_lease(files_env):
    web, factory, _, _ = files_env
    _, items = pending_collection(web, factory)
    with factory.begin() as session:
        session.get(ApiChannel, 1).paused = True
    assert claim(factory) is None
    with factory.begin() as session:
        session.get(ApiChannel, 1).paused = False
        first = session.get(ApiItem, UUID(items[0]['id']))
        first.result_url = None
    assert claim(factory) is None
    with factory.begin() as session:
        first = session.get(ApiItem, UUID(items[0]['id']))
        first.result_bytes = image_bytes()
        first.lease_token, first.lease_until = uuid4(), utcnow() + timedelta(minutes=5)
    assert claim(factory) is None
    with factory.begin() as session:
        first = session.get(ApiItem, UUID(items[0]['id']))
        first.lease_until = utcnow() - timedelta(seconds=1)
    assert claim(factory)[2] == 'collecting'


def test_safe_collection_still_obeys_global_ten_lease_limit(files_env):
    web, factory, _, _ = files_env
    task_id, _ = create(web, 12)
    with factory.begin() as session:
        items = session.scalars(select(ApiItem).where(ApiItem.task_id == UUID(task_id))
                                .order_by(ApiItem.position)).all()
        for item in items[:-1]:
            item.state, item.result_bytes = 'collecting', image_bytes()
        items[-1].state = 'uncertain'
    reservations = [claim(factory) for _ in range(12)]
    assert len([value for value in reservations if value]) == 10
    assert len({value[0] for value in reservations if value}) == 10
