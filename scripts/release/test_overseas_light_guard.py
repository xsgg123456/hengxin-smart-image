"""Run real release checks in an isolated filesystem."""
import importlib.util
import os
from pathlib import Path
import signal
import stat
import tempfile
from unittest import SkipTest


def test_publication_lock_blocks_unprivileged_rename_and_restores_modes():
    if os.name != 'posix' or os.geteuid() != 0:
        raise SkipTest('Requires POSIX root execution')
    spec = importlib.util.spec_from_file_location('light_deploy', Path(__file__).with_name('overseas-light-deploy.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory(prefix='light-permission-lock-') as temporary:
        root = Path(temporary)
        root.chmod(0o755)
        app, work, outside = root / 'app', root / 'work', root / 'outside'
        (app / 'frontend/dist').mkdir(parents=True)
        work.mkdir(mode=0o700)
        outside.mkdir(mode=0o777)
        app.chmod(0o777)
        (app / 'frontend').chmod(0o777)
        outside.chmod(0o777)
        def attempt():
            pid = os.fork()
            if pid == 0:
                try:
                    os.setgid(65534)
                    os.setuid(65534)
                    os.rename(app / 'frontend/dist', app / 'frontend/moved')
                    os._exit(0)
                except PermissionError:
                    os._exit(2)
                except BaseException:
                    os._exit(3)
            return os.waitstatus_to_exitcode(os.waitpid(pid, 0)[1])
        before = attempt()
        assert before == 0, before
        os.rename(app / 'frontend/moved', app / 'frontend/dist')
        with module.front.protect_publication_directories(app, work):
            assert stat.S_IMODE(app.stat().st_mode) == 0o755
            assert stat.S_IMODE((app / 'frontend').stat().st_mode) == 0o755
            assert attempt() == 2
        assert stat.S_IMODE(app.stat().st_mode) == 0o777
        assert stat.S_IMODE((app / 'frontend').stat().st_mode) == 0o777
        assert (work / 'FRONTEND_PERMISSIONS_RESTORED.json').is_file()
        work2 = root / 'work2'
        work2.mkdir(mode=0o700)
        try:
            with module.front.protect_publication_directories(app, work2):
                raise ValueError('injected failure')
        except ValueError:
            pass
        assert stat.S_IMODE(app.stat().st_mode) == 0o777
        assert stat.S_IMODE((app / 'frontend').stat().st_mode) == 0o777


def test_writable_asset_directory_and_unguarded_install_are_rejected():
    if os.name != 'posix' or os.geteuid() != 0:
        raise SkipTest('Requires POSIX root execution')
    spec = importlib.util.spec_from_file_location('light_deploy', Path(__file__).with_name('overseas-light-deploy.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory(prefix='light-untrusted-directory-') as temporary:
        root = Path(temporary)
        (root / 'assets').mkdir()
        (root / 'assets').chmod(0o777)
        try:
            module.front.require_asset_directory(root, root / 'assets')
        except RuntimeError:
            pass
        else:
            raise AssertionError('writable asset directory was accepted')
        assert stat.S_IMODE((root / 'assets').stat().st_mode) == 0o777
        try:
            module.install_frontend(root, root / 'app', root / 'backup')
        except RuntimeError as error:
            assert 'not protected' in str(error)
        else:
            raise AssertionError('unguarded install was accepted')


def test_concurrent_publications_do_not_unlock_each_other():
    if os.name != 'posix' or os.geteuid() != 0:
        raise SkipTest('Requires POSIX root execution')
    spec = importlib.util.spec_from_file_location('light_deploy', Path(__file__).with_name('overseas-light-deploy.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory(prefix='light-concurrent-publication-') as temporary:
        root = Path(temporary)
        app, work, work2 = root / 'app', root / 'work', root / 'work2'
        (app / 'frontend/dist').mkdir(parents=True)
        work.mkdir(mode=0o700)
        work2.mkdir(mode=0o700)
        app.chmod(0o777)
        (app / 'frontend').chmod(0o777)
        with module.front.protect_publication_directories(app, work):
            pid = os.fork()
            if pid == 0:
                try:
                    with module.front.protect_publication_directories(app, work2):
                        os._exit(3)
                except BlockingIOError:
                    os._exit(0)
                except BaseException:
                    os._exit(2)
            assert os.waitstatus_to_exitcode(os.waitpid(pid, 0)[1]) == 0
            assert stat.S_IMODE(app.stat().st_mode) == 0o755
            assert stat.S_IMODE((app / 'frontend').stat().st_mode) == 0o755
        assert stat.S_IMODE(app.stat().st_mode) == 0o777
        assert stat.S_IMODE((app / 'frontend').stat().st_mode) == 0o777

if __name__ == '__main__':
    test_publication_lock_blocks_unprivileged_rename_and_restores_modes()
    test_writable_asset_directory_and_unguarded_install_are_rejected()
    test_concurrent_publications_do_not_unlock_each_other()
    print('ISOLATED_RELEASE_CHECKS_PASS')
