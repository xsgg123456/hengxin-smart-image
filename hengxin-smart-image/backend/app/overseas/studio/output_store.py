"""The same ledger and original-file storage serve automatic and manual receipt."""
from types import SimpleNamespace
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import select

from app.core.config import get_settings
from app.overseas.tasks.models import ExecutionObject
from .models import Picture, OutputFile, Turn
from .files import read


def row_data(job, target, file, identity):
    picture = file.width is not None and file.height is not None
    data = dict(id=identity, task_id=job.task_id, turn_id=UUID(job.payload['turnId']),
        name=file.name, bucket=get_settings().minio_bucket,
        object_key=f'studio/{"pictures" if picture else "outputs"}/{job.task_id}/{identity}',
        content_type=file.content_type, size_bytes=len(file.data), checksum=file.checksum,
        source_path=target)
    if picture:
        data.update(width=file.width, height=file.height)
    return data


def save(factory, job, target, file, identity, store, guard):
    data = row_data(job, target, file, identity)
    model = Picture if 'width' in data else OutputFile
    result = dict(id=str(identity), kind='picture' if model is Picture else 'file')
    with factory.begin() as session:
        guard(session)
        existing = session.get(model, identity)
        if existing:
            if any(getattr(existing, key) != data[key] for key in
                   ('task_id', 'turn_id', 'object_key', 'checksum', 'source_path')):
                raise ValueError('Conflicting output identity')
            return result
        ledger = session.scalar(select(ExecutionObject).where(
            ExecutionObject.bucket == data['bucket'], ExecutionObject.object_key == data['object_key']))
        if ledger and (ledger.job_id != job.id or ledger.task_id != job.task_id):
            raise ValueError('Conflicting output ownership')
        if ledger is None:
            session.add(ExecutionObject(task_id=job.task_id, job_id=job.id,
                bucket=data['bucket'], object_key=data['object_key']))
    # Persist ownership before external IO. Holding the task lock during publish
    # serializes it with deletion, completion and another receipt of this file.
    with factory.begin() as session:
        guard(session)
        if session.get(model, identity):
            return result
        record = SimpleNamespace(**data)
        try:
            read(store, record)
        except HTTPException:
            store.put(record, file.data)
            read(store, record)
        guard(session)
        session.add(model(**data))
        session.flush()
        refresh_receipt(session, job.id)
    return result


def refresh_receipt(session, job_id):
    """A recovered frozen original resolves its old automatic-save warning."""
    from app.overseas.execution.models import Job
    job = session.get(Job, job_id)
    result = dict(job.result or {})
    status = result.get('deliveryStatus')
    if job.status != 'succeeded' or not status or status.get('state') != 'partial':
        return
    order = set(result.get('deliveryOrder', []))
    turn_id = UUID(job.payload['turnId'])
    saved = {str(identity) for model in (Picture, OutputFile) for identity in
             session.scalars(select(model.id).where(model.turn_id == turn_id))}
    count = len(order & saved)
    if count <= status['saved']:
        return
    complete = count == status['expected'] and len(order) == status['expected']
    result['deliveryStatus'] = dict(status, saved=count,
                                   state='complete' if complete else 'partial')
    if complete:
        session.get(Turn, turn_id).delivery_error = None
    job.result = result
    job.version += 1
