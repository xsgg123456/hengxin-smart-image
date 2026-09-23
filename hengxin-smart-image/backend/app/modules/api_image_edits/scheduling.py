"""Admission under the shared channel row lock; capacity is counted by task."""
from .models import ApiTask

TASK_CONCURRENCY = 5
IMAGES_PER_TASK = 10


def candidates(session, pending, leased, blocked):
    grouped = {}
    for item in pending:
        grouped.setdefault(item.task_id, []).append(item)
    tasks = {key: session.get(ApiTask, key) for key in grouped}
    admitted = [key for key in grouped if tasks[key].state in {'running', 'uncertain'}]
    # Leases are authoritative even for legacy/inconsistent summary states.
    for item in leased:
        if item.task_id not in admitted:
            admitted.append(item.task_id)
    waiting = [key for key in grouped if key not in admitted]
    allowed = admitted + waiting[:max(0, TASK_CONCURRENCY - len(admitted))]
    # Spread claims across the admitted tasks instead of filling one task first.
    counts = {key: sum(item.task_id == key for item in leased) for key in allowed}
    result = []
    for key in sorted(allowed, key=lambda key: counts[key]):
        if counts[key] >= IMAGES_PER_TASK:
            continue
        items = grouped[key]
        current = next((item for item in leased if item.task_id == key), items[0])
        batch = (current.position - 1) // IMAGES_PER_TASK
        if blocked:
            result.extend(item for item in items if item.state == 'collecting'
                          and (item.result_url or item.result_bytes))
        else:
            result.extend(item for item in items
                          if (item.position - 1) // IMAGES_PER_TASK == batch)
    return result
