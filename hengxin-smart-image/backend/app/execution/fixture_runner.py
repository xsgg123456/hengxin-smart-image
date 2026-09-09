import time
from io import BytesIO
from uuid import UUID
from starlette.datastructures import UploadFile
from sqlalchemy import select
from app.core.config import get_settings
from app.db.session import session_factory
from app.modules.files.service import save_upload
from app.modules.files.validation import validate_image
from app.modules.tasks.claims import claim, cancelled, locked_execution, mark_uncertain
from app.modules.tasks.models import RoundRecord, TaskRecord, TaskSource, ResultSlotRecord
from app.modules.tasks.results import publish_results
from app.resource_models import FileRecord, UserRecord
from app.storage.minio_store import get_store
from app.worker.leases import heartbeat


def run_generation(job_id, factory=None, store=None, after_upload=None):
    settings = get_settings()
    if settings.app_env != 'test' or not settings.enable_fixture_executor:
        return  # A disabled executor never consumes already accepted durable work.
    factory, store = factory or session_factory(), store or get_store()
    token = claim(factory, job_id)
    if token is None:
        return
    try:
        with heartbeat(factory, job_id, token):
            deadline = time.monotonic() + settings.fixture_delay_seconds
            while time.monotonic() < deadline:
                if cancelled(factory, job_id, token):
                    return
                time.sleep(min(.1, max(0, deadline - time.monotonic())))
            if cancelled(factory, job_id, token):
                return
            outputs = generate_files(factory, store, job_id, token)
            if after_upload:
                after_upload()
            if cancelled(factory, job_id, token):
                return
            publish_results(factory, job_id, token, outputs)
    except Exception:
        # The external object store may have accepted writes: never retry blindly.
        with factory.begin() as session:
            task, round, job = locked_execution(session, job_id)
            if job and job.claim_token == token and job.status == 'running':
                mark_uncertain(round, job)


def generate_files(factory, store, job_id, token):
    with factory() as session:
        round = session.scalar(select(RoundRecord).where(RoundRecord.job_id == UUID(str(job_id))))
        task = session.get(TaskRecord, round.task_id)
        sources = session.scalars(select(TaskSource).where(TaskSource.task_id == task.id)
                                  .order_by(TaskSource.slot)).all()
        slots = session.scalars(select(ResultSlotRecord).where(ResultSlotRecord.task_id == task.id)
                                .order_by(ResultSlotRecord.slot)).all()
        targets = [slot.slot for slot in slots if round.target is None or slot.slot == round.target]
        files = [session.get(FileRecord, source.file_id) for source in sources]
        user = session.get(UserRecord, round.operator_id)
        session.expunge_all()
    outputs = []
    for slot in targets:
        if cancelled(factory, job_id, token):
            return []
        source = files[slot % len(files)]
        stream = store.open(source)
        try:
            raw = b''.join(stream.stream(64 * 1024))
        finally:
            stream.close()
            stream.release_conn()
        validated = validate_image(UploadFile(filename=source.name, file=BytesIO(raw)))
        with factory() as session:
            file = save_upload(session, store, user, validated)
            outputs.append(file.id)
    return outputs
