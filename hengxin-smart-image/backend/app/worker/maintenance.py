"""Explicit maintenance: stop intake, prove idle, restart, restore intake on failure."""
import argparse
import subprocess
import time

from sqlalchemy import func, select

from app.db.session import session_factory
from app.models import Job
from app.worker.celery_app import celery_app

SERVICE = 'hengxin-vps-codex-worker.service'


def inspect_one(control, node, method):
    result = getattr(control.inspect(destination=[node], timeout=5), method)()
    if not isinstance(result, dict) or node not in result or not isinstance(result[node], list):
        raise RuntimeError('Worker inspection unavailable; restart refused')
    return result[node]


def database_idle(factory):
    with factory() as session:
        return session.scalar(select(func.count()).select_from(Job).where(
            Job.status.in_(['running', 'collecting', 'cancelling', 'uncertain']))) == 0


def drain_restart(control, factory, node, restart, wait_seconds=0):
    queues = inspect_one(control, node, 'active_queues')
    names = [queue['name'] for queue in queues]
    if not names or len(set(names)) != len(names):
        raise RuntimeError('No unambiguous active queues; restart refused')
    removed = []
    try:
        for name in names:
            # Record before sending: lost acknowledgment must still restore intake.
            removed.append(name)
            result = control.cancel_consumer(name, destination=[node], reply=True, timeout=5)
            if not result or not any(isinstance(row.get(node), dict) and 'ok' in row[node] for row in result):
                raise RuntimeError('Consumer cancellation unconfirmed; restart refused')
        deadline = time.monotonic() + wait_seconds
        while True:
            if inspect_one(control, node, 'active_queues'):
                raise RuntimeError('Worker still consuming; restart refused')
            busy = any([inspect_one(control, node, method)
                        for method in ('active', 'reserved', 'scheduled')])
            if not busy and database_idle(factory):
                restart()
                removed.clear()  # New worker starts its configured consumers.
                return
            if time.monotonic() >= deadline:
                raise RuntimeError('Tasks still active or uncertain; restart deferred')
            time.sleep(min(5, max(0, deadline - time.monotonic())))
    finally:
        for name in removed:
            control.add_consumer(name, destination=[node], reply=True, timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--node', required=True)
    parser.add_argument('--wait-seconds', type=int, default=0)
    parser.add_argument('--restart', action='store_true')
    args = parser.parse_args()
    if args.wait_seconds < 0:
        parser.error('wait-seconds must be nonnegative')
    if not args.restart:
        print({key: len(inspect_one(celery_app.control, args.node, key))
               for key in ('active', 'reserved', 'scheduled')})
        print({'database_idle': database_idle(session_factory())})
        return
    drain_restart(celery_app.control, session_factory(), args.node,
                  lambda: subprocess.run(['systemctl', 'restart', SERVICE], check=True),
                  args.wait_seconds)
    print('Worker restarted after drain; verify heartbeat and active queues.')


if __name__ == '__main__':
    main()
