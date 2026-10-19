"""Run inside one live worker's environment; only operate its proven Celery node."""
import importlib
import json
from pathlib import Path
import sys
import time

import codex_auth_runtime as r


def inspect(control, node, name):
    response = getattr(control.inspect(destination=[node], timeout=3), name)()
    r.require(isinstance(response, dict) and isinstance(response.get(node), list),
              'Worker inspection unavailable; no stop permitted')
    return response[node]


def identify(control, pid, domain):
    stats = control.inspect(timeout=3).stats()
    r.require(isinstance(stats, dict), 'Worker statistics unavailable')
    matches = [(node, value) for node, value in stats.items()
               if isinstance(value, dict) and value.get('pid') == pid]
    r.require(len(matches) == 1, 'No unique Celery node matches actual MainPID')
    node, value = matches[0]
    r.require(value.get('pool', {}).get('max-concurrency') == 5, 'Worker pool is not five')
    queues = inspect(control, node, 'active_queues')
    r.require([q.get('name') for q in queues] == [r.DOMAINS[domain]['queue']], 'Unexpected worker queues')
    return node


def database_idle(factory, domain):
    from sqlalchemy import text
    if domain == 'domestic':
        query = ("SELECT (SELECT count(*) FROM job_records WHERE status NOT IN "
                 "('queued','succeeded','failed','cancelled')) + "
                 "(SELECT count(*) FROM api_edit_turns WHERE status NOT IN "
                 "('queued','candidate','waiting_user','adopted','failed','cancelled'))")
    else:
        query = ("SELECT count(*) FROM overseas_jobs WHERE status NOT IN "
                 "('queued','succeeded','failed','cancelled') OR "
                 "(process_id IS NOT NULL AND NOT process_exited)")
    with factory() as session:
        return session.scalar(text(query)) == 0


def ack(value, node):
    return isinstance(value, list) and any(isinstance(row, dict)
        and isinstance(row.get(node), dict) and 'ok' in row[node] for row in value)


def drain_stop(control, factory, domain, node, work, wait_seconds=60):
    config = r.DOMAINS[domain]
    queue, attempted_stop = config['queue'], False
    try:
        reply = control.cancel_consumer(queue, destination=[node], reply=True, timeout=3)
        r.require(ack(reply, node), 'Consumer cancellation unconfirmed; no stop permitted')
        deadline, stable = time.monotonic() + wait_seconds, 0
        while True:
            r.require(not inspect(control, node, 'active_queues'), 'Consumer remains active; no stop permitted')
            busy = any([inspect(control, node, name) for name in ('active', 'reserved', 'scheduled')])
            idle = database_idle(factory, domain)
            stable = stable + 1 if not busy and idle else 0
            r.require(time.monotonic() <= deadline, 'Worker drain deadline exceeded; no stop permitted')
            if stable == 2:
                # The parent never starts another executor unless this subprocess proves success.
                r.private(work / (domain + '-stage.json'), {'phase': 'drained-stop-requested', 'node': node})
                attempted_stop = True
                r.run('systemctl', 'stop', config['unit'], timeout=30)
                r.require(r.run('systemctl', 'show', config['unit'], '-p', 'MainPID', '--value') == '0',
                          'Worker stop unconfirmed')
                r.private(work / (domain + '-stage.json'), {'phase': 'stopped', 'node': node})
                return
            time.sleep(min(2, max(0, deadline - time.monotonic())))
    finally:
        if not attempted_stop:
            reply = control.add_consumer(queue, destination=[node], reply=True, timeout=3)
            r.require(ack(reply, node), 'Old intake restoration unconfirmed; inspect manually')


def main():
    domain, mode, pid, directory = sys.argv[1:]
    r.require(domain in r.DOMAINS and mode in ('verify', 'drain-stop'), 'Unknown worker probe mode')
    config = r.DOMAINS[domain]
    control = importlib.import_module(config['module']).celery_app.control
    factory = importlib.import_module('app.overseas.db' if domain == 'overseas' else 'app.db.session').session_factory()
    node = identify(control, int(pid), domain)
    if mode == 'drain-stop':
        drain_stop(control, factory, domain, node, Path(directory))
    print(json.dumps({'node': node, 'pid': int(pid), 'queue': config['queue'], 'pool': 5, 'mode': mode}))


if __name__ == '__main__':
    main()
