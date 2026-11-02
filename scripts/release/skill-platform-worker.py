"""Inspect or pause only the existing idle overseas consumer; never stop its process."""
import importlib.util
import json
from pathlib import Path
import sys

spec = importlib.util.spec_from_file_location('account_worker', Path(__file__).with_name('account-worker.py'))
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)


def idle(control, factory, node):
    from sqlalchemy import text
    busy = any(a.inspect(control, node, name) for name in ('active', 'reserved', 'scheduled'))
    with factory() as session:
        pending = session.scalar(text("SELECT count(*) FROM overseas_jobs WHERE status NOT IN "
            "('succeeded','failed','cancelled') OR (process_id IS NOT NULL AND NOT process_exited)"))
    a.r.require(not busy and pending == 0, 'Overseas work remains; keep existing consumer running')


def main():
    from app.overseas.execution.worker import celery_app
    from app.overseas.db import session_factory
    mode, pid, expected = sys.argv[1:]
    control, factory = celery_app.control, session_factory()
    if mode in ('resume','paused'):
        response = control.inspect(destination=[expected], timeout=3).stats()
        a.r.require(response and response.get(expected, {}).get('pid') == int(pid), 'Worker identity drift')
        if mode == 'resume':
            a.r.require(a.ack(control.add_consumer('overseas.cli', destination=[expected], reply=True, timeout=3), expected),
                        'Consumer resume unconfirmed')
            a.r.require(a.identify(control, int(pid), 'overseas') == expected, 'Resumed consumer differs')
        else:
            a.r.require(not a.inspect(control, expected, 'active_queues'),'Consumer is no longer paused')
            idle(control,factory,expected)
        node = expected
    else:
        node = a.identify(control, int(pid), 'overseas')
        idle(control, factory, node)
        if mode == 'pause':
            try:
                a.r.require(a.ack(control.cancel_consumer('overseas.cli', destination=[node], reply=True, timeout=3), node),
                            'Consumer pause unconfirmed')
                a.r.require(not a.inspect(control, node, 'active_queues'), 'Consumer remains active')
                idle(control, factory, node)
            except BaseException:
                a.r.require(a.ack(control.add_consumer('overseas.cli', destination=[node], reply=True, timeout=3), node),
                            'Failed pause: consumer restoration unconfirmed')
                raise
        else:
            a.r.require(mode == 'idle', 'Unknown mode')
    print(json.dumps({'node':node, 'pid':int(pid), 'mode':mode}))


if __name__ == '__main__':
    main()
