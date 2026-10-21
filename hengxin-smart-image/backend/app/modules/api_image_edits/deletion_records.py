"""Erase business payloads after physical cleanup, retaining only content-free facts."""
from uuid import UUID
from sqlalchemy import delete, select, update
from app.models import Job, Outbox, utcnow
from app.capacity.models import CapacityReservation
from app.modules.files.variants import ImageVariants
from app.modules.management.api_stats.backfill import preserve
from app.modules.management.api_stats.models import ApiUsageFact
from app.retention.models import RetentionEntry, RetentionObject
from app.retention.events import object_result
from .conversation_models import Conversation, ConversationEvent, ConversationTurn
from .deletion_files import related
from .models import ApiAttempt, ApiDispatch, ApiFile, ApiItem, ApiOperation, ApiVersion


def erase(session, task, manifest, objects):
    items, conversations, turns, _ = related(session, task)
    item_ids, conversation_ids = [i.id for i in items], [c.id for c in conversations]
    turn_ids, job_ids = [t.id for t in turns], [t.job_id for t in turns]
    preserve(session, task_id=task.id)
    session.execute(update(ApiUsageFact).where(ApiUsageFact.task_id == task.id).values(task_name='已删除任务'))
    session.execute(delete(ConversationEvent).where(ConversationEvent.conversation_id.in_(conversation_ids)))
    session.execute(update(ConversationTurn).where(ConversationTurn.id.in_(turn_ids)).values(base_turn_id=None))
    session.execute(delete(ConversationTurn).where(ConversationTurn.id.in_(turn_ids)))
    session.execute(delete(Outbox).where(Outbox.job_id.in_(job_ids)))
    session.execute(delete(Job).where(Job.id.in_(job_ids)))
    session.execute(delete(Conversation).where(Conversation.id.in_(conversation_ids)))
    session.execute(delete(RetentionEntry).where(RetentionEntry.domain == 'api_cli',
        RetentionEntry.resource_id.in_(conversation_ids)))
    session.execute(delete(CapacityReservation).where(
        CapacityReservation.owner_id.in_([*item_ids, *turn_ids])))
    session.execute(delete(ApiVersion).where(ApiVersion.item_id.in_(item_ids)))
    session.execute(delete(ApiAttempt).where(ApiAttempt.item_id.in_(item_ids)))
    session.execute(delete(ApiItem).where(ApiItem.id.in_(item_ids)))
    session.execute(delete(ApiOperation).where(ApiOperation.task_id == task.id))
    session.execute(delete(ApiDispatch).where(ApiDispatch.id == task.id))
    session.delete(task)
    session.flush()
    files = [UUID(value) for value in manifest['files']]
    session.execute(delete(ImageVariants).where(ImageVariants.domain == 'api-image-edits',
        ImageVariants.file_id.in_(files)))
    session.execute(delete(ApiFile).where(ApiFile.id.in_(files)))
    for bucket, key in objects:
        receipt = session.scalar(select(RetentionObject).where(RetentionObject.bucket == bucket,
            RetentionObject.object_key == key).with_for_update())
        if receipt is not None:
            object_result(session, receipt.id, utcnow(), removed=True)
            session.delete(receipt)
