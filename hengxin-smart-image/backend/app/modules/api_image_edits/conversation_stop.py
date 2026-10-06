"""Resolve uncertain cancellation on the owning worker, never on the API host."""
import os
import signal
import time
from app.core.config import get_settings
from app.execution.process import same_process
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
    try:
        args = (identity['pid'], identity['boot'], identity['birth'])
        if same_process(*args):
            os.killpg(identity['pid'], signal.SIGTERM)
            for _ in range(25):
                if not same_process(*args):
                    break
                time.sleep(.2)
            if same_process(*args):
                os.killpg(identity['pid'], signal.SIGKILL)
                return True  # Next delivery verifies death before releasing capacity.
    except (OSError, KeyError):
        return True
    with factory.begin() as session:
        _, _, conversation, turn, job = locked(session, job_id)
        if turn.status == 'uncertain' and turn.cancel_requested and turn.process_identity == identity:
            finish(session, conversation, turn, job, 'cancelled', '原执行进程已停止')
            published(session, turn.id)
    return True
