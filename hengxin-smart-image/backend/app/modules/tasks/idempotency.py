from app.core.idempotency import fingerprint_payload, lookup_request
from .models import TaskRequest
from app.contracts.business import Accepted


def fingerprint(body):
    data = body.model_dump()
    if not data.get('restartExpired'):
        data.pop('restartExpired', None)
    # Preserve legacy request hashes and distinguish an omitted base (freeze current)
    # from explicit null (no successful result). Other established fields stay unchanged.
    for name in ('baseVersionId', 'annotationFileId'):
        if name not in body.model_fields_set:
            data.pop(name, None)
    return fingerprint_payload(data)


def replay(session, user_id, operation, target, key, body_hash):
    request = lookup_request(session, TaskRequest, user_id, operation, target, key, body_hash)
    if request:
        return Accepted(taskId=str(request.task_id), roundId=str(request.round_id), state='排队中')
    return None
