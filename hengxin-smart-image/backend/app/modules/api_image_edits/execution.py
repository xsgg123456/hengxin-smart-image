from io import BytesIO
from types import SimpleNamespace

from fastapi import HTTPException

from app.models import utcnow
from app.modules.files.validation import DECODE_SLOTS, _decode_image
from .claims import claim, owned, start_attempt
from .config import get_api_settings
from .downloads import download_result
from .files import new_record, read_bytes
from .heartbeat import heartbeat
from .models import ApiFile, ApiItem, ApiTask
from .outcomes import collection_failure, failure, save_response
from .relay import RelayClient, RelayError
from .state import event, refresh_task, release


def inputs(factory, item_id, store):
    with factory() as session:
        item = session.get(ApiItem, item_id)
        task = session.get(ApiTask, item.task_id)
        source = session.get(ApiFile, item.source_id)
        material = session.get(ApiFile, task.material_id)
        # Detach before object-store I/O; no long-lived DB transaction during requests.
        session.expunge_all()
    return (read_bytes(store, source), source.content_type,
            read_bytes(store, material), material.content_type, task.prompt, task.parameters)


def collect(factory, store, item_id, token, downloader):
    with factory() as session:
        item = session.get(ApiItem, item_id)
        task = session.get(ApiTask, item.task_id)
        url, data, owner = item.result_url, item.result_bytes, task.owner_id
    try:
        if data is None:
            data = downloader(url)
        upload = SimpleNamespace(file=BytesIO(data), filename='result.png', content_type=None)
        with DECODE_SLOTS:
            image = _decode_image(upload, get_api_settings().max_download_bytes)
    except HTTPException:
        collection_failure(factory, item_id, token, permanent=True)
        return
    except Exception:
        collection_failure(factory, item_id, token)
        return
    # Persist staging metadata before external writes; a crash cannot publish a ghost.
    with factory.begin() as session:
        _, item = owned(session, item_id, token)
        if not item:
            return
        record = new_record(owner, image)
        session.add(record)
        session.flush()
        record_id = record.id
    try:
        store.put(record, image.data)
    except Exception:
        collection_failure(factory, item_id, token)
        return
    with factory.begin() as session:
        gate, item = owned(session, item_id, token)
        if not item:
            return
        session.get(ApiFile, record_id).status = 'ready'
        item.result_id, item.state, item.error = record_id, 'succeeded', None
        item.result_url = item.result_bytes = None
        task = session.get(ApiTask, item.task_id)
        event(task, f'第 {item.position} 张已完成')
        release(gate)
        refresh_task(session, task)


def execute_next(factory, store, client=None, downloader=download_result):
    claimed = claim(factory)
    if not claimed:
        return False
    item_id, token, state = claimed
    with heartbeat(factory, item_id, token):
        _execute_claim(factory, store, client, downloader, item_id, token, state)
    return True


def _execute_claim(factory, store, client, downloader, item_id, token, state):
    if state != 'collecting':
        try:
            args = inputs(factory, item_id, store)
        except Exception:
            failure(factory, item_id, token, 'permanent', 'input_storage_unavailable')
            return True
        relay = client or RelayClient()
        try:
            if hasattr(relay, 'preflight'):
                relay.preflight(*args)
        except RelayError as error:
            failure(factory, item_id, token, error.kind, error.code, error.retry_after)
            return True
        if not start_attempt(factory, item_id, token):
            return True
        try:
            result = relay.generate(*args)
        except RelayError as error:
            failure(factory, item_id, token, error.kind, error.code, error.retry_after)
            return True
        except Exception:
            # An unexpected post-send failure is not safe to replay.
            failure(factory, item_id, token, 'uncertain', 'request_outcome_unknown')
            return True
        if not save_response(factory, item_id, token, result):
            return True
    collect(factory, store, item_id, token, downloader)
