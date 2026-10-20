"""Fair task admission under the shared channel lock; waiting frees task slots."""
from .models import ApiTask
from .state import aware

TASK_CONCURRENCY = 5
IMAGES_PER_TASK = 10


def candidates(session, pending, leased, blocked=False, now=None):
    from .retry_policy import database_now
    now = now or database_now(session)
    grouped = {}
    for item in pending:
        grouped.setdefault(item.task_id, []).append(item)
    tasks = {key: session.get(ApiTask, key) for key in grouped}
    counts = {key: sum(item.task_id == key for item in leased) for key in grouped}
    admitted = [key for key in grouped if counts[key]]
    batches = {}
    for key, items in grouped.items():
        live = [item for item in leased if item.task_id == key and item.lease_token]
        batches[key] = (min(item.position for item in live or items) - 1) // IMAGES_PER_TASK
    def ready(item):
        return (item.state != 'uncertain' and
                (not item.next_attempt_at or aware(item.next_attempt_at) <= now) and
                (item.position - 1) // IMAGES_PER_TASK == batches[item.task_id])
    def order(key):
        return aware(tasks[key].last_send_at or tasks[key].created_at), str(key)
    waiting = sorted((key for key in grouped if key not in admitted and
                     any(ready(item) for item in grouped[key])), key=order)
    allowed = admitted + waiting[:max(0, TASK_CONCURRENCY - len(admitted))]
    result = []
    for key in sorted(allowed, key=lambda key: (counts[key], *order(key))):
        if counts[key] < IMAGES_PER_TASK:
            result.extend(item for item in grouped[key] if ready(item))
    return result
