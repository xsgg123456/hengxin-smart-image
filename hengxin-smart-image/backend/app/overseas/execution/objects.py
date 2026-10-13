"""Track storage before upload, including late/rejected outputs and interrupted collection."""
from contextlib import contextmanager
from contextvars import ContextVar
from types import SimpleNamespace
from uuid import UUID
from app.overseas.tasks.models import ExecutionObject
from app.overseas.tasks.queries import get_task
from . import claims

_owner = ContextVar('overseas_output_owner', default=None)


@contextmanager
def collecting(factory, job, token):
    marker = _owner.set((factory, job.id, job.task_id, token))
    try:
        yield
    finally:
        _owner.reset(marker)


def put(store, row, data):
    record = SimpleNamespace(**row) if isinstance(row, dict) else row
    owner = _owner.get()
    if owner is None:
        # Direct protocol validation in isolated tests; production always uses collecting().
        return store.put(record, data)
    factory, job_id, task_id, token = owner
    with factory.begin() as session:
        get_task(session, task_id, lock=True)
        if not claims.valid(claims.locked_job(session, job_id), token):
            raise ValueError('Output ownership lost')
        session.add(ExecutionObject(task_id=task_id, job_id=job_id,
            bucket=record.bucket, object_key=record.object_key))
    # Keep ownership locked during the write. The ledger is already durable if storage fails.
    with factory.begin() as session:
        get_task(session, task_id, lock=True)
        if not claims.valid(claims.locked_job(session, job_id), token):
            raise ValueError('Output ownership lost')
        store.put(record, data)
