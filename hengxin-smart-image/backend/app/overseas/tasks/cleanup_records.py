"""Explicit dependency order; bulk SQL does not invoke ORM cascade hooks."""
from sqlalchemy import delete, select
from app.overseas.materials.models import Material, ParseVersion
from app.overseas.pictures.models import Picture, PictureVersion
from app.overseas.plans.models import Plan
from app.overseas.studio.models import Conversation, Turn, Upload, Transcript, Picture as StudioPicture
from app.overseas.studio.models import MaterialVisibility, ConversationDeletion, OutputFile
from app.overseas.execution.models import Job, JobOutbox, ExecutionEvent
from app.overseas.archives.models import Archive
from .models import Task, TaskSku, TaskEvent, TaskOutbox, TaskRequest, RequirementsReview, ExecutionObject


def erase(session, task_id):
    for record in session.scalars(select(Archive).where(Archive.task_id == task_id)):
        record.task_id = None
    session.flush()
    for model, condition in [
        (TaskOutbox, TaskOutbox.event_id.in_(select(TaskEvent.id).where(TaskEvent.task_id == task_id))),
        (TaskEvent, TaskEvent.task_id == task_id), (TaskRequest, TaskRequest.task_id == task_id),
        (RequirementsReview, RequirementsReview.task_id == task_id),
        (ParseVersion, ParseVersion.material_id.in_(select(Material.id).where(Material.task_id == task_id))),
        (Material, Material.task_id == task_id), (Upload, Upload.task_id == task_id),
        (MaterialVisibility, MaterialVisibility.task_id == task_id),
        (Transcript, Transcript.task_id == task_id), (OutputFile, OutputFile.task_id == task_id),
        (StudioPicture, StudioPicture.task_id == task_id), (Turn, Turn.task_id == task_id),
        (ConversationDeletion, ConversationDeletion.task_id == task_id),
        (Conversation, Conversation.task_id == task_id),
        (PictureVersion, PictureVersion.picture_id.in_(select(Picture.id).where(Picture.task_id == task_id))),
        (Picture, Picture.task_id == task_id), (Plan, Plan.task_id == task_id),
        (ExecutionObject, ExecutionObject.task_id == task_id),
        (ExecutionEvent, ExecutionEvent.task_id == task_id),
        (JobOutbox, JobOutbox.job_id.in_(select(Job.id).where(Job.task_id == task_id))),
        (Job, Job.task_id == task_id), (TaskSku, TaskSku.task_id == task_id), (Task, Task.id == task_id),
    ]:
        session.execute(delete(model).where(condition).execution_options(synchronize_session=False))
