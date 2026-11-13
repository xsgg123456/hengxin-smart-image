"""Verify process-death and PostgreSQL transaction fences on local test resources."""
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

import joint_studio_fence as fence
import engine as release_engine


@pytest.mark.skipif(sys.platform != 'linux' or os.geteuid() != 0,
                    reason='requires root Linux process and flock semantics')
def test_child_keeps_process_fence_after_parent_death():
    temporary = tempfile.TemporaryDirectory(prefix='hx-fence-uid-', dir='/tmp')
    root = Path(temporary.name)
    root.chmod(0o755)
    work, signals = root / 'work', root / 'signals'
    work.mkdir(mode=0o700)
    signals.mkdir(mode=0o700)
    os.chown(signals, 1001, 1001)
    ready, release, done = (signals / name for name in ('ready', 'release', 'done'))
    script_dir = Path(__file__).resolve().parent
    child_code = ("import os,pathlib,sys,time\n"
                  "ready,release,done=map(pathlib.Path,sys.argv[1:])\n"
                  "ready.write_text(str(os.getuid()))\n"
                  "while not release.exists(): time.sleep(.02)\n"
                  "done.write_text('finished')\n")
    parent_code = ("import subprocess,sys\nfrom pathlib import Path\nfrom types import SimpleNamespace\n"
                   "sys.path.insert(0,sys.argv[1])\nimport joint_studio_fence as fence\n"
                   "u=SimpleNamespace(WORK=Path(sys.argv[2]),safe=lambda path:None)\n"
                   "with fence.hold(u) as fd:\n"
                   " p=subprocess.Popen([sys.executable,'-c',sys.argv[3],*sys.argv[4:]],pass_fds=(fd,),"
                   "user=1001,group=1001,extra_groups=[986],"
                   "stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)\n"
                   " p.wait()\n")
    parent = subprocess.Popen([sys.executable, '-c', parent_code, str(script_dir), str(work), child_code,
                               str(ready), str(release), str(done)],
                              stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    def wait(path):
        deadline = time.monotonic() + 10
        while not path.exists() and time.monotonic() < deadline:
            time.sleep(.02)
        assert path.exists(), 'timed out waiting for isolated process'
    try:
        wait(ready)
        assert ready.read_text() == '1001'
        parent.kill()
        parent.wait(timeout=5)
        u = SimpleNamespace(WORK=work, safe=lambda path: None)
        with pytest.raises(RuntimeError, match='still running'):
            with fence.hold(u, timeout=.2):
                pass
        release.write_text('continue')
        wait(done)
        with fence.hold(u, timeout=5) as descriptor:
            fence.assert_held(u, descriptor)
            with pytest.raises(RuntimeError, match='descriptor'):
                fence.assert_held(u, True)
    finally:
        release.touch()
        if parent.poll() is None:
            parent.kill()
            parent.wait(timeout=5)
        temporary.cleanup()


@pytest.mark.skipif(not os.environ.get('TEST_DOMESTIC_STUDIO_DATABASE_URL'),
                    reason='requires an explicit disposable local PostgreSQL database')
def test_database_fence_waits_for_the_prior_transaction():
    url = make_url(os.environ['TEST_DOMESTIC_STUDIO_DATABASE_URL'])
    if (url.drivername != 'postgresql+psycopg' or url.host not in ('127.0.0.1', 'localhost')
            or not (url.database or '').endswith('_test')):
        pytest.fail('Only a disposable local *_test database is allowed')
    module_path = (Path(__file__).resolve().parents[3] /
                   'hengxin-smart-image/backend/app/modules/domestic_studio/migration_barrier.py')
    spec = importlib.util.spec_from_file_location('domestic_migration_barrier_test', module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = create_engine(url)
    try:
        with engine.connect() as first, ThreadPoolExecutor(max_workers=1) as pool:
            transaction = first.begin()
            module.acquire(first)
            def attempt():
                with engine.begin() as second:
                    module.acquire(second)
                    return 'released'
            future = pool.submit(attempt)
            time.sleep(.25)
            assert not future.done()
            transaction.commit()
            assert future.result(timeout=5) == 'released'
    finally:
        engine.dispose()


@pytest.mark.skipif(sys.platform != 'linux' or os.geteuid() != 0
                    or not os.environ.get('TEST_DOMESTIC_STUDIO_DATABASE_URL'),
                    reason='requires root Linux and the disposable local PostgreSQL test database')
def test_real_native_identity_waits_for_database_fence():
    url = make_url(os.environ['TEST_DOMESTIC_STUDIO_DATABASE_URL'])
    if (url.drivername != 'postgresql+psycopg' or url.host not in ('127.0.0.1', 'localhost')
            or not (url.database or '').endswith('_test')):
        pytest.fail('Only a disposable local *_test database is allowed')
    root = Path(__file__).resolve().parents[3] / 'hengxin-smart-image'
    module_path = root / 'backend/app/modules/domestic_studio/migration_barrier.py'
    spec = importlib.util.spec_from_file_location('native_migration_barrier_test', module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    db = create_engine(url)
    ctx = {'python': sys.executable, 'cwd': str(root / 'backend'), 'user': 1001, 'group': 1001,
           'extra_groups': [986], 'env': dict(os.environ, DATABASE_URL=url.render_as_string(hide_password=False),
                                               PYTHONPATH=str(root / 'backend'))}
    u = SimpleNamespace(RELEASE=root, native_run=release_engine.u.native_run)
    try:
        with db.connect() as first, ThreadPoolExecutor(max_workers=1) as pool:
            transaction = first.begin()
            module.acquire(first)
            future = pool.submit(fence.wait_database, u, ctx)
            time.sleep(.5)
            assert not future.done()
            transaction.commit()
            assert future.result(timeout=10) is None
    finally:
        db.dispose()
