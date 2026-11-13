"""Exercise the proposed publisher under Linux identities and restricted capabilities."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

import pytest
from sqlalchemy.engine import make_url

import domestic_studio_wiring as wiring
from test_domestic_studio_wiring import original


@pytest.mark.skipif(sys.platform != 'linux' or os.geteuid() != 0 or not shutil.which('bwrap')
                    or not os.environ.get('TEST_DOMESTIC_STUDIO_DATABASE_URL'),
                    reason='requires an isolated root Linux runtime and explicit test database')
def test_real_publisher_readiness_and_socket_identity():
    db = make_url(os.environ['TEST_DOMESTIC_STUDIO_DATABASE_URL'])
    if (db.drivername != 'postgresql+psycopg' or db.host not in ('127.0.0.1', 'localhost')
            or not (db.database or '').endswith('_test')):
        pytest.fail('Only a disposable local *_test database is allowed')
    backend = Path(__file__).resolve().parents[3] / 'hengxin-smart-image/backend'
    with tempfile.TemporaryDirectory(prefix='hx-domestic-publisher-', dir='/tmp') as name:
        root = Path(name)
        root.chmod(0o755)
        domestic, uds = root / 'domestic', root / 'socket'
        domestic.mkdir(mode=0o755)
        (domestic / 'local-skills').mkdir(mode=0o755)
        (domestic / 'skill-transfers').mkdir(mode=0o700)
        uds.mkdir(mode=0o750)
        environment = dict(os.environ, APP_ENV='production', HX_BUSINESS_CONTEXT='domestic',
            DATABASE_URL=db.render_as_string(hide_password=False),
            MINIO_ACCESS_KEY='not-used-by-publisher', MINIO_SECRET_KEY='not-used-by-publisher',
            DOMESTIC_SKILL_ROOT=wiring.SKILLS, DOMESTIC_SKILL_TRANSFER_ROOT=wiring.TRANSFERS,
            DOMESTIC_SKILL_PUBLISH_SOCKET=wiring.SOCKET, PYTHONPATH=str(backend), PYTHONUNBUFFERED='1')
        command = [shutil.which('bwrap'), '--die-with-parent', '--ro-bind', '/', '/',
            '--tmpfs', '/var/lib', '--dir', '/var/lib/hengxin-domestic',
            '--bind', str(domestic), '/var/lib/hengxin-domestic', '--tmpfs', '/run',
            '--dir', wiring.SOCKET_DIR, '--bind', str(uds), wiring.SOCKET_DIR,
            '--chdir', str(backend), '--cap-drop', 'ALL', '--cap-add', 'CAP_CHOWN',
            sys.executable, '-B', '-m', 'app.modules.domestic_studio.skill_publisher']
        with tempfile.TemporaryFile() as output:
            process = subprocess.Popen(command, env=environment, stdout=output, stderr=subprocess.STDOUT)
            path = uds / 'publisher.sock'
            try:
                deadline = time.monotonic() + 20
                while not path.exists() and process.poll() is None and time.monotonic() < deadline:
                    time.sleep(.1)
                if not path.exists():
                    output.seek(0)
                    pytest.fail('Publisher did not start: ' + output.read().decode(errors='replace'))
                assert path.stat().st_uid == 0 and path.stat().st_gid == 10001
                assert path.stat().st_mode & 0o777 == 0o660
                candidate = wiring.candidate(original(), '/opt/hengxin-unified-releases/domestic-test')
                health = candidate['services'][wiring.PUBLISHER]['healthcheck']['test'][-1]
                subprocess.run([sys.executable, '-c', health.replace(wiring.SOCKET, str(path))],
                               check=True, timeout=5)

                def connect_as(uid, gid):
                    def identity():
                        os.setgroups([])
                        os.setgid(gid)
                        os.setuid(uid)
                    code = ("import socket,sys; s=socket.socket(socket.AF_UNIX); s.settimeout(3); "
                            "s.connect(sys.argv[1]); s.sendall(b'GET /health HTTP/1.0\\r\\n\\r\\n'); "
                            "assert s.recv(128).split()[1] == b'200'")
                    return subprocess.run([sys.executable, '-c', code, str(path)],
                                          preexec_fn=identity, capture_output=True, timeout=5)

                assert connect_as(10001, 10001).returncode == 0
                assert connect_as(1001, 1001).returncode != 0
            finally:
                process.terminate()
                process.wait(timeout=10)
