from fastapi import HTTPException
from sqlalchemy import select
from app.contracts.business import DeletionReceipt
from app.models import Job
from app.modules.files.deletions import logical_delete
from .models import TaskRecord, RoundRecord, ACTIVE
from .claims import end


def delete_task(session, user, task_id):
    task = session.scalar(select(TaskRecord).where(TaskRecord.id == task_id).with_for_update()
                          .execution_options(populate_existing=True))
    if not task or task.deleted_at:
        raise HTTPException(404, '任务不存在')
    receipt = logical_delete(session, task, 'task', user)
    rounds = session.scalars(select(RoundRecord).where(RoundRecord.task_id == task.id,
        RoundRecord.status.in_(ACTIVE)).with_for_update()).all()
    for round in rounds:
        job = session.scalar(select(Job).where(Job.id == round.job_id).with_for_update())
        round.cancel_requested = True
        if round.status == 'queued':
            end(session, round, job, 'cancelled')
        elif round.status != 'uncertain':
            round.status = 'cancelling'
            # Keep Job running to let its live heartbeat preserve ownership until it stops.
    session.commit()
    return DeletionReceipt(id=str(receipt.resource_id), operatorId=str(receipt.operator_id),
                           deletedAt=receipt.deleted_at.isoformat(), resourceType='task')
