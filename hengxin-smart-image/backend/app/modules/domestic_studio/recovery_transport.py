"""Use the existing metadata-only recovery queue with domestic isolation."""
import time
from fastapi import HTTPException
from app.overseas.studio import recovery_transport as shared

PREFIX = 'domestic:studio:recovery:'


def request(operation, actor_id, conversation_id, files=()):
    return shared.request(operation, actor_id, actor_id, conversation_id, files, prefix=PREFIX)


def request_archive(actor_id, archive_id, conversation_id):
    return shared.request('archive', actor_id, archive_id, conversation_id, prefix=PREFIX)


def handle_native(factory, message):
    from . import recovery_files
    message = shared.NativeRequest.model_validate(message)
    if message.expires_at <= time.time():
        raise HTTPException(503, shared.UNAVAILABLE)
    if message.operation == 'archive':
        from app.core.config import get_settings
        from app.storage.minio_store import get_store
        from . import archive_service, maintenance_lock
        from .archive_models import Archive
        with factory() as session:
            archive = session.get(Archive, message.task_id)
            if (archive is None or archive.owner_id != message.actor_id
                    or archive.source_conversation_id != message.conversation_id):
                raise HTTPException(404, '归档不存在')
        with maintenance_lock.hold(get_settings(), message.conversation_id):
            archive_service.complete(factory, get_store(), message.task_id, message.actor_id)
        return {'completed': True}
    if message.task_id != message.actor_id:
        raise HTTPException(503, shared.UNAVAILABLE)
    if message.operation == 'available':
        return recovery_files.available(factory, message.actor_id, message.conversation_id)
    from app.storage.minio_store import get_store
    return recovery_files.recover(factory, message.actor_id, message.conversation_id, message.files, get_store())


def consume_once(factory):
    return shared.consume_once(factory, prefix=PREFIX, handler=handle_native)
