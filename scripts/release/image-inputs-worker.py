"""Release-only worker controls. Never print environment values."""
import os
from pathlib import Path
import subprocess
import sys
import time

SERVICE = 'hengxin-vps-codex-worker.service'


def native_run(mode, wait):
    pid = int(subprocess.check_output(['systemctl', 'show', SERVICE, '-p', 'MainPID', '--value']))
    if pid <= 0:
        raise RuntimeError('Native worker has no live PID')
    cwd = Path(os.readlink(f'/proc/{pid}/cwd'))
    env = dict(entry.split(b'=', 1) for entry in Path(f'/proc/{pid}/environ').read_bytes().split(b'\0') if entry)
    env = {os.fsdecode(k): os.fsdecode(v) for k, v in env.items()}
    env['PYTHONPATH'] = str(cwd)
    subprocess.run([str(cwd / '.venv/bin/python'), str(Path(__file__).resolve()), mode, wait], cwd=cwd, env=env, check=True)


def check(control, node, name):
    response = getattr(control.inspect(destination=[node], timeout=5), name)()
    if not isinstance(response, dict) or not isinstance(response.get(node), list):
        raise RuntimeError('Worker inspection unavailable')
    return response[node]


def api_control(mode, wait):
    from app.modules.api_image_edits.celery_app import celery_app
    from app.db.session import session_factory
    from sqlalchemy import text
    control = celery_app.control
    replies = control.inspect(timeout=5).ping()
    if not isinstance(replies, dict) or len(replies) != 1:
        raise RuntimeError('Expected exactly one API worker')
    node = next(iter(replies))
    if mode == 'api-resume':
        reply = control.add_consumer('api_image_edits', destination=[node], reply=True, timeout=5)
        assert reply and any('ok' in row.get(node, {}) for row in reply)
        return
    if mode == 'api-verify':
        assert {q['name'] for q in check(control, node, 'active_queues')} == {'api_image_edits'}
        stats = control.inspect(destination=[node], timeout=5).stats()
        assert stats[node]['pool']['max-concurrency'] == 5
        print('API_WORKER_READY_POOL_5')
        return
    removed = []
    try:
        names = [q['name'] for q in check(control, node, 'active_queues')]
        assert names == ['api_image_edits']
        for name in names:
            removed.append(name)
            reply = control.cancel_consumer(name, destination=[node], reply=True, timeout=5)
            assert reply and any('ok' in row.get(node, {}) for row in reply)
        deadline = time.monotonic() + int(wait)
        while True:
            assert not check(control, node, 'active_queues')
            busy = any([check(control, node, method) for method in ('active', 'reserved', 'scheduled')])
            with session_factory()() as session:
                pending = session.scalar(text("SELECT (SELECT count(*) FROM api_image_tasks WHERE state NOT IN ('succeeded','failed','partial_failed')) + (SELECT count(*) FROM api_image_items WHERE state NOT IN ('succeeded','failed'))"))
            if not busy and pending == 0:
                removed.clear()
                print('API_DRAINED')
                return
            if time.monotonic() >= deadline:
                raise RuntimeError('API busy or uncertain; no force stop allowed')
            time.sleep(5)
    finally:
        for name in removed:
            control.add_consumer(name, destination=[node], reply=True, timeout=5)


def main():
    raise SystemExit("旧公网发布入口已退役；使用 scripts/release/intranet/release.py 并明确 --scope。")


if __name__ == '__main__':
    main()
