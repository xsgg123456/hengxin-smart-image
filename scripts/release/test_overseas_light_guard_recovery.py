"""Run real release checks in an isolated filesystem."""
import importlib.util
import os
from pathlib import Path
import signal
import stat
import tempfile
from unittest import SkipTest


def test_sigkill_requires_identity_checked_recovery_before_retry():
    if os.name != 'posix' or os.geteuid() != 0:
        raise SkipTest('Requires POSIX root execution')
    spec = importlib.util.spec_from_file_location('light_deploy', Path(__file__).with_name('overseas-light-deploy.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory(prefix='light-forced-exit-') as temporary:
        root = Path(temporary)
        app, work, work2 = root / 'app', root / 'work', root / 'work2'
        (app / 'frontend/dist').mkdir(parents=True)
        work.mkdir(mode=0o700)
        work2.mkdir(mode=0o700)
        app.chmod(0o777)
        (app / 'frontend').chmod(0o777)
        reader, writer = os.pipe()
        pid = os.fork()
        if pid == 0:
            os.close(reader)
            try:
                with module.front.protect_publication_directories(app, work):
                    os.write(writer, b'1')
                    signal.pause()
            finally:
                os._exit(2)
        os.close(writer)
        assert os.read(reader, 1) == b'1'
        os.close(reader)
        os.kill(pid, signal.SIGKILL)
        os.waitpid(pid, 0)
        assert stat.S_IMODE(app.stat().st_mode) == 0o755
        assert stat.S_IMODE((app / 'frontend').stat().st_mode) == 0o755
        try:
            with module.front.protect_publication_directories(app, work2):
                raise AssertionError('unrecovered publication was accepted')
        except RuntimeError as error:
            assert 'require recovery' in str(error)
        assert not (work / 'FRONTEND_PERMISSIONS_RESTORED.json').exists()
        original = (work / 'FRONTEND_PERMISSIONS.json').read_bytes()
        os.rename(app / 'frontend', app / 'original-frontend')
        (app / 'frontend').mkdir(mode=0o700)
        try:
            module.front.guard.recover_publication_directories(app, work)
        except RuntimeError as error:
            assert 'identity changed' in str(error)
        else:
            raise AssertionError('recovery accepted a different inode')
        assert stat.S_IMODE((app / 'frontend').stat().st_mode) == 0o700
        assert stat.S_IMODE(app.stat().st_mode) == 0o755
        (app / 'frontend').rmdir()
        os.rename(app / 'original-frontend', app / 'frontend')
        module.front.guard.recover_publication_directories(app, work)
        assert (work / 'FRONTEND_PERMISSIONS.json').read_bytes() == original
        assert stat.S_IMODE(app.stat().st_mode) == 0o777
        assert stat.S_IMODE((app / 'frontend').stat().st_mode) == 0o777
        try:
            with module.front.protect_publication_directories(app, work):
                raise AssertionError('old receipt was overwritten')
        except RuntimeError as error:
            assert 'Existing permission receipt' in str(error)
        with module.front.protect_publication_directories(app, work2):
            assert stat.S_IMODE((app / 'frontend').stat().st_mode) == 0o755
        assert stat.S_IMODE((app / 'frontend').stat().st_mode) == 0o777


def test_sigquit_restores_permissions():
    if os.name != 'posix' or os.geteuid() != 0:
        raise SkipTest('Requires POSIX root execution')
    spec = importlib.util.spec_from_file_location('light_deploy', Path(__file__).with_name('overseas-light-deploy.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory(prefix='light-quit-exit-') as temporary:
        root = Path(temporary)
        app, work = root / 'app', root / 'work'
        (app / 'frontend/dist').mkdir(parents=True)
        work.mkdir(mode=0o700)
        app.chmod(0o777)
        (app / 'frontend').chmod(0o777)
        reader, writer = os.pipe()
        pid = os.fork()
        if pid == 0:
            os.close(reader)
            try:
                with module.front.protect_publication_directories(app, work):
                    os.write(writer, b'1')
                    signal.pause()
            except SystemExit:
                os._exit(0)
            os._exit(3)
        os.close(writer)
        assert os.read(reader, 1) == b'1'
        os.close(reader)
        os.kill(pid, signal.SIGQUIT)
        assert os.waitstatus_to_exitcode(os.waitpid(pid, 0)[1]) == 0
        assert stat.S_IMODE(app.stat().st_mode) == 0o777
        assert stat.S_IMODE((app / 'frontend').stat().st_mode) == 0o777
        assert (work / 'FRONTEND_PERMISSIONS_RESTORED.json').is_file()


def test_interrupted_restoration_receipt_does_not_block_recovery():
    if os.name != 'posix' or os.geteuid() != 0:
        raise SkipTest('Requires POSIX root execution')
    spec = importlib.util.spec_from_file_location('light_deploy', Path(__file__).with_name('overseas-light-deploy.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory(prefix='light-receipt-interrupt-') as temporary:
        root = Path(temporary)
        app, work = root / 'app', root / 'work'
        (app / 'frontend/dist').mkdir(parents=True)
        work.mkdir(mode=0o700)
        app.chmod(0o777)
        (app / 'frontend').chmod(0o777)
        reader, writer = os.pipe()
        pid = os.fork()
        if pid == 0:
            os.close(reader)
            original = os.replace
            def pause_before_receipt(src, dst, *args, **kwargs):
                if dst == 'FRONTEND_PERMISSIONS_RESTORED.json':
                    os.write(writer, b'1')
                    signal.pause()
                return original(src, dst, *args, **kwargs)
            os.replace = pause_before_receipt
            with module.front.protect_publication_directories(app, work):
                pass
            os._exit(3)
        os.close(writer)
        assert os.read(reader, 1) == b'1'
        os.close(reader)
        os.kill(pid, signal.SIGKILL)
        os.waitpid(pid, 0)
        assert list(work.glob('.FRONTEND_PERMISSIONS_RESTORED.json.*.new'))
        assert stat.S_IMODE(app.stat().st_mode) == 0o777
        module.front.guard.recover_publication_directories(app, work)
        assert (work / 'FRONTEND_PERMISSIONS_RESTORED.json').is_file()
        assert stat.S_IMODE((app / 'frontend').stat().st_mode) == 0o777


def test_pending_write_failure_cannot_publish_partial_state():
    if os.name != 'posix' or os.geteuid() != 0:
        raise SkipTest('Requires POSIX root execution')
    spec = importlib.util.spec_from_file_location('light_deploy', Path(__file__).with_name('overseas-light-deploy.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory(prefix='light-pending-failure-') as temporary:
        root = Path(temporary)
        app, work, work2 = root / 'app', root / 'work', root / 'work2'
        (app / 'frontend/dist').mkdir(parents=True)
        work.mkdir(mode=0o700)
        work2.mkdir(mode=0o700)
        app.chmod(0o777)
        (app / 'frontend').chmod(0o777)
        original = module.front.guard.json.dump
        def partial(value, stream, *args, **kwargs):
            if isinstance(value, dict) and 'work' in value:
                stream.write('{"id": "partial')
                stream.flush()
                raise OSError('injected storage failure')
            return original(value, stream, *args, **kwargs)
        module.front.guard.json.dump = partial
        try:
            try:
                with module.front.protect_publication_directories(app, work):
                    raise AssertionError('partial state was accepted')
            except OSError:
                pass
        finally:
            module.front.guard.json.dump = original
        assert not (root / '.hengxin-overseas-light.pending').exists()
        assert stat.S_IMODE(app.stat().st_mode) == 0o777
        with module.front.protect_publication_directories(app, work2):
            assert stat.S_IMODE((app / 'frontend').stat().st_mode) == 0o755
        assert stat.S_IMODE((app / 'frontend').stat().st_mode) == 0o777

if __name__ == '__main__':
    test_sigkill_requires_identity_checked_recovery_before_retry()
    test_sigquit_restores_permissions()
    test_interrupted_restoration_receipt_does_not_block_recovery()
    test_pending_write_failure_cannot_publish_partial_state()
    print('ISOLATED_RELEASE_CHECKS_PASS')
