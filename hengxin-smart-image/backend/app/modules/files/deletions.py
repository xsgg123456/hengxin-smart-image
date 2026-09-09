"""Caller owns the transaction and resource lock; this service never deletes stored bytes."""
from typing import Literal

from app.models import utcnow
from app.modules.auth.permissions import authorize
from app.resource_models import DeletionRecord


def logical_delete(session, resource, resource_type: Literal['template', 'task', 'archive'], user):
    authorize(user)
    if resource_type not in ('template', 'task', 'archive'):
        raise ValueError('Unsupported logical deletion resource')
    if resource.deleted_at is not None:
        return None
    resource.deleted_at = utcnow()
    record = DeletionRecord(resource_type=resource_type, resource_id=resource.id,
                            operator_id=user.id, deleted_at=resource.deleted_at)
    session.add(record)
    session.flush()
    return record
