from uuid import uuid4
from sqlalchemy import func, select
from app.models import utcnow
from app.resource_models import FileRecord
from .claims import end, locked_execution, valid
from .models import ImageVersion, ResultSlotRecord


def publish_results(factory, job_id, token, outputs):
    """Only this short transaction makes uploaded files visible as task results."""
    with factory.begin() as session:
        task, round, job = locked_execution(session, job_id)
        if not job or not valid(task, round, job, token):
            return False
        slots = session.scalars(select(ResultSlotRecord).where(ResultSlotRecord.task_id == task.id)
                               .order_by(ResultSlotRecord.slot)).all()
        targets = [slot for slot in slots if round.target is None or slot.slot == round.target]
        if len(outputs) != len(targets):
            raise ValueError('Result count must match frozen output slots')
        for slot, file_id in zip(targets, outputs):
            file = session.get(FileRecord, file_id)
            if not file or file.status != 'ready' or file.deleted_at:
                raise ValueError('Output file is not readable')
            version = 1 + (session.scalar(select(func.max(ImageVersion.version)).where(
                ImageVersion.slot_id == slot.id)) or 0)
            record = ImageVersion(id=uuid4(), slot_id=slot.id, round_id=round.id,
                                  version=version, file_id=file.id)
            session.add(record)
            session.flush()
            slot.current_version_id, slot.error = record.id, None
        end(session, round, job, 'succeeded')
        return True
