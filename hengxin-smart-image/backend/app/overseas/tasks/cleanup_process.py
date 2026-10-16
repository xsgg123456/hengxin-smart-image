"""Process-group exit is mandatory; uncertainty never authorizes destructive cleanup."""
import os
import signal
from datetime import timezone
from pathlib import Path
from sqlalchemy import select
from app.core.config import get_settings
from app.execution.process import same_process
from app.db.timestamps import utcnow
from app.overseas.execution.models import Job, TERMINAL
from .models import TaskDeletion


def group_alive(job):
    if os.name != 'posix' or not Path('/proc/sys/kernel/random/boot_id').is_file():
        raise OSError('Process verification unavailable')
    if Path('/proc/sys/kernel/random/boot_id').read_text().strip() != job.process_boot:
        return False
    for entry in Path('/proc').iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            fields = (entry / 'stat').read_text().rsplit(')', 1)[1].split()
        except (FileNotFoundError, ProcessLookupError):
            continue
        if fields[0] != 'Z' and int(fields[2]) == job.process_id:
            return True
    return False


def confirmed(session, task_id):
    node = get_settings().worker_node_name
    for job in session.scalars(select(Job).where(Job.task_id == task_id)):
        if job.worker_node and job.worker_node != node:
            return False
        if job.status not in TERMINAL:
            # The runner owns its Python collector until it reaches terminal state.
            # For a lost worker only reconciliation can establish an exit receipt.
            if (job.status == 'uncertain' and job.cancel_requested and job.worker_node == node
                    and all((job.process_id, job.process_boot, job.process_started))):
                try:
                    if same_process(job.process_id, job.process_boot, job.process_started):
                        receipt = session.get(TaskDeletion, task_id)
                        elapsed = (utcnow() - receipt.created_at.replace(tzinfo=timezone.utc)).total_seconds()
                        os.killpg(job.process_id, signal.SIGKILL if elapsed >= 5 else signal.SIGTERM)
                except (OSError, ValueError):
                    pass
            return False
        if job.execution_count and not job.process_exited:
            return False
        if job.process_id:
            if not all((job.process_boot, job.process_started)):
                return False
            try:
                if group_alive(job):
                    return False
            except (OSError, ValueError):
                return False
    return True
