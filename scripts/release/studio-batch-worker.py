"""Read fixed worker identity even while its consumer is paused."""
import importlib.util
import json
from pathlib import Path
import sys

spec = importlib.util.spec_from_file_location('platform_worker', Path(__file__).with_name('skill-platform-worker.py'))
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)


def status(control, pid, expected):
    stats = control.inspect(timeout=3).stats()
    w.a.r.require(isinstance(stats, dict), 'Worker statistics unavailable')
    matches = [node for node, value in stats.items() if isinstance(value, dict) and value.get('pid') == pid]
    w.a.r.require(matches == [expected], 'Worker identity drift')
    w.a.r.require(stats[expected].get('pool', {}).get('max-concurrency') == 5, 'Worker pool is not five')
    queues = [q.get('name') for q in w.a.inspect(control, expected, 'active_queues')]
    w.a.r.require(queues in ([], ['overseas.cli']), 'Unexpected worker queues')
    return {'node':expected, 'pid':pid, 'paused':not queues}


if __name__ == '__main__':
    if sys.argv[1] == 'status':
        from app.overseas.execution.worker import celery_app
        print(json.dumps(status(celery_app.control, int(sys.argv[2]), sys.argv[3])))
    else:
        w.main()
