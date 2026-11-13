"""Resolve uncertain cancellation on the owning worker, never on the API host."""
import os
import time
from app.core.config import get_settings
from app.execution.process import same_process
from app.execution.process_group import group_alive
from app.execution.verified_stop import stopped
from app.capacity.admission import published
from .conversation_runtime import finish, locked


def stop_uncertain(factory, job_id):
    with factory() as session:
        _, _, _, turn, job = locked(session, job_id)
        if not job or turn.status != 'uncertain' or not turn.cancel_requested:
            return False
        identity = turn.process_identity
        if not identity or identity.get('node') != get_settings().worker_node_name:
            return True  # No proof; retain fence for administrator investigation.
    if not stopped(identity, get_settings().worker_node_name, inspect=same_process,
                   group_alive=group_alive, kill=lambda pid, sig: os.killpg(pid, sig), sleep=time.sleep):
        return True
    with factory.begin() as session:
        _, _, conversation, turn, job = locked(session, job_id)
        if turn.status == 'uncertain' and turn.cancel_requested and turn.process_identity == identity:
            finish(session, conversation, turn, job, 'cancelled', '原执行进程已停止')
            published(session, turn.id)
    return True
