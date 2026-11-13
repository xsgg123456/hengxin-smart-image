"""Fail-closed maintenance gates used only by the joint LAN release."""
import os
from pathlib import Path
import stat
import time

DIRECTORY = '/var/lib/hengxin-domestic/release-gate'
ENVIRONMENT = 'HX_RELEASE_GATE_DIR'
READY_PATHS = frozenset(('/api/v1/health/ready', '/api/overseas/v1/health/ready',
                         '/api/identity/v1/config'))


def marker_open(name):
    directory = os.environ.get(ENVIRONMENT)
    if not directory:
        return True
    if directory != DIRECTORY or name not in ('workers', 'ingress'):
        return False
    try:
        root = Path(directory)
        info = root.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_gid != 0
                or stat.S_IMODE(info.st_mode) != 0o755):
            return False
        if not hasattr(os, 'O_NOFOLLOW'):
            return False
        descriptor = os.open(root / name, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            info = os.fstat(descriptor)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_gid != 0
                    or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o644 or info.st_size > 16):
                return False
            return os.read(descriptor, 17) == b'open\n'
        finally:
            os.close(descriptor)
    except (OSError, ValueError):
        return False


def wait_for_workers(stop=None):
    while not marker_open('workers'):
        if stop is not None:
            if stop.wait(.5):
                return False
        else:
            time.sleep(.5)
    return True


def guard_celery(app):
    from celery.signals import worker_init
    def before_consumer(sender, **_):
        if getattr(sender, 'app', None) is app:
            wait_for_workers()
    worker_init.connect(before_consumer, weak=False)


class ReleaseGateMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        kind = scope['type']
        if kind in ('http', 'websocket') and not marker_open('ingress'):
            if kind == 'websocket':
                await send({'type': 'websocket.close', 'code': 1013})
                return
            if scope.get('method') != 'GET' or scope.get('path') not in READY_PATHS:
                from starlette.responses import JSONResponse
                response = JSONResponse({'detail': '系统维护中，请稍后重试'}, status_code=503,
                                        headers={'Cache-Control': 'no-store'})
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)
