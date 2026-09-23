from io import BytesIO
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor

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
from .state import event, refresh_task, release_item
from .versions import execution_inputs, publish_result
from .scheduling import IMAGES_PER_TASK


def inputs(factory, item_id, store):
    with factory() as session:
        item = session.get(ApiItem, item_id)
        task = session.get(ApiTask, item.task_id)
        revision = execution_inputs(session, item, task)
        if revision and item.revision_snapshot is not None:
            records, prompt = revision
            parameters = task.parameters
        elif revision:
            source, material, prompt = revision
        else:
            source = session.get(ApiFile, item.source_id)
            material = session.get(ApiFile, task.material_id)
            prompt = task.prompt
        # Detach before object-store I/O; no long-lived DB transaction during requests.
        session.expunge_all()
    if revision and item.revision_snapshot is not None:
        images = []
        for record in records:
            data = read_bytes(store, record)
            upload = SimpleNamespace(file=BytesIO(data), filename=record.name,
                                     content_type=record.content_type)
            with DECODE_SLOTS:
                _decode_image(upload, get_api_settings().max_download_bytes)
            images.append((data, record.content_type))
        return (*images[0], *images[1], prompt, parameters, images[2:])
    return (read_bytes(store, source), source.content_type,
            read_bytes(store, material) if material else None,
            material.content_type if material else None, prompt, task.parameters)


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
        item.state, item.error = 'succeeded', None
        item.result_url = item.result_bytes = None
        task = session.get(ApiTask, item.task_id)
        publish_result(session, item, task, record_id)
        event(task, f'第 {item.position} 张已完成')
        release_item(item)
        refresh_task(session, task)


def execute_next(factory, store, client=None, downloader=download_result):
    claimed = claim(factory)
    if not claimed:
        return False
    item_id, token, state = claimed
    with heartbeat(factory, item_id, token):
        _execute_claim(factory, store, client, downloader, item_id, token, state)
    return True


def execute_batch(factory, store, client=None, downloader=download_result):
    # Each execution opens its own sessions. DB admission enforces the same cap
    # even when several Celery deliveries race across processes.
    with ThreadPoolExecutor(max_workers=IMAGES_PER_TASK, thread_name_prefix='api-image') as pool:
        futures = [pool.submit(execute_next, factory, store, client, downloader)
                   for _ in range(IMAGES_PER_TASK)]
        return sum(bool(future.result()) for future in futures)


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
            kind = 'retryable' if error.kind == 'permanent' else error.kind
            failure(factory, item_id, token, kind, error.code, error.retry_after)
            return True
        except Exception:
            # The call has ended locally; the user opted into bounded retries.
            failure(factory, item_id, token, 'uncertain', 'request_outcome_unknown')
            return True
        if not save_response(factory, item_id, token, result):
            return True
    collect(factory, store, item_id, token, downloader)
