"""Stop only the exact process identity recorded by the owning worker."""
import os
import signal
import time

from app.execution.process import same_process
from app.execution.process_group import group_alive as has_live_group


def stopped(identity, worker_node, *, inspect=same_process, group_alive=has_live_group, kill=None, sleep=time.sleep):
    if not isinstance(identity, dict) or identity.get('node') != worker_node:
        return False
    if (type(identity.get('pid')) is not int or identity['pid'] <= 1
            or not isinstance(identity.get('boot'), str) or not identity['boot']
            or not isinstance(identity.get('birth'), str) or not identity['birth']):
        return False
    kill = kill or (lambda pid, sig: os.killpg(pid, sig))
    try:
        args = (identity['pid'], identity['boot'], identity['birth'])
        if inspect(*args):
            kill(identity['pid'], signal.SIGTERM)
            for _ in range(25):
                if not group_alive(identity['pid'], identity['boot']):
                    return True
                sleep(.2)
            # Never signal a group after its original leader's identity is lost.
            if inspect(*args):
                force = getattr(signal, 'SIGKILL', None)
                if force is not None:
                    kill(identity['pid'], force)
            return False
        if group_alive(identity['pid'], identity['boot']):
            return False
    except (OSError, KeyError, TypeError, ValueError):
        return False
    return True
