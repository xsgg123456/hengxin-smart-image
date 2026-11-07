"""Run real release checks in an isolated filesystem."""
import importlib.util
import os
from pathlib import Path
import signal
import stat
import tempfile
from unittest import SkipTest


def test_install_preserves_unrelated_directory_and_stale_temp():
    spec = importlib.util.spec_from_file_location('light_deploy', Path(__file__).with_name('overseas-light-deploy.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory(prefix='light-installer-test-') as temporary:
        root = Path(temporary)
        source, app, backup = root / 'source', root / 'app', root / 'backup'
        (source / 'frontend/dist/assets/newfolder').mkdir(parents=True)
        (source / 'frontend/dist/index.html').write_text('new index')
        (source / 'frontend/dist/assets/newfolder/new.js').write_text('new asset')
        (source / 'frontend/package.json').write_text('{"version":"0.2.67"}')
        (source / 'release.json').write_text('{}')
        (app / 'frontend/dist/assets/newfolder').mkdir(parents=True)
        (app / 'frontend/dist/index.html').write_text('old index')
        (app / 'frontend/package.json').write_text('{"version":"0.2.66"}')
        outside = root / 'outside'
        outside.mkdir(mode=0o700)
        if os.name != 'nt':
            (app / 'frontend/dist/unrelated').symlink_to(outside, target_is_directory=True)
        stale = app / 'frontend/dist/index.html.sku-new'
        stale.write_text('untouched')
        names = ('frontend/dist/index.html', 'frontend/dist/assets/newfolder/new.js', 'frontend/package.json')
        files = {name: module.r.digest(source / name) for name in names}
        module.r.verify_package = lambda *_: {'files': files}
        work = root / 'work'
        work.mkdir(mode=0o700)
        with module.front.protect_publication_directories(app, work):
            module.install_frontend(source, app, backup)
        assert (app / 'frontend/dist/index.html').read_text() == 'new index'
        assert stale.read_text() == 'untouched'
        if os.name != 'nt':
            assert stat.S_IMODE(outside.stat().st_mode) == 0o700
            assert stat.S_IMODE((app / 'frontend/dist/assets/newfolder').stat().st_mode) == 0o755
        work2 = root / 'work2'
        work2.mkdir(mode=0o700)
        with module.front.protect_publication_directories(app, work2):
            module.frontend.rollback(app, backup)
        assert (app / 'frontend/dist/index.html').read_text() == 'old index'
        assert stale.read_text() == 'untouched'
        if os.name != 'nt':
            assert stat.S_IMODE(outside.stat().st_mode) == 0o700
        assert not list((app / 'frontend/dist').glob('*.overseas-light-*'))
        replace = os.replace
        def fail_replace(*_args, **_kwargs):
            raise OSError('injected replace failure')
        os.replace = fail_replace
        try:
            try:
                module.atomic_frontend_copy(source / 'frontend/dist/index.html', app / 'frontend/dist/index.html')
            except OSError:
                pass
            else:
                raise AssertionError('replace failure not propagated')
        finally:
            os.replace = replace
        assert (app / 'frontend/dist/index.html').read_text() == 'old index'
        assert stale.read_text() == 'untouched'
        assert not list((app / 'frontend/dist').glob('*.overseas-light-*'))


def test_missing_asset_directory_is_rejected_without_creation():
    spec = importlib.util.spec_from_file_location('light_deploy', Path(__file__).with_name('overseas-light-deploy.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory(prefix='light-directory-race-') as temporary:
        root, outside = Path(temporary) / 'root', Path(temporary) / 'outside'
        root.mkdir()
        outside.mkdir(mode=0o700)
        rejected = False
        try:
            module.front.require_asset_directory(root, root / 'child')
        except (OSError, RuntimeError):
            rejected = True
        assert rejected and not (root / 'child').exists()


def test_parent_swap_cannot_write_or_delete_outside():
    if os.name != 'posix':
        raise SkipTest('Requires POSIX filesystem semantics')
    spec = importlib.util.spec_from_file_location('light_deploy', Path(__file__).with_name('overseas-light-deploy.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for action in ('copy', 'unlink'):
        with tempfile.TemporaryDirectory(prefix='light-parent-race-') as temporary:
            root, outside = Path(temporary) / 'root', Path(temporary) / 'outside'
            (root / 'victim').mkdir(parents=True)
            outside.mkdir(mode=0o700)
            source = root / 'source'
            source.write_text('new')
            (root / 'victim/index.html').write_text('old')
            (outside / 'index.html').write_text('outside sentinel')
            original_open = os.open
            swapped = False
            def swap(path, flags, *args, **kwargs):
                nonlocal swapped
                parent = kwargs.get('dir_fd')
                if path == 'victim' and parent is not None and not swapped:
                    swapped = True
                    os.rename('victim', 'moved-victim', src_dir_fd=parent, dst_dir_fd=parent)
                    os.symlink(str(outside), 'victim', dir_fd=parent, target_is_directory=True)
                return original_open(path, flags, *args, **kwargs)
            os.open = swap
            rejected = False
            try:
                try:
                    target = root / 'victim/index.html'
                    if action == 'copy':
                        module.front.atomic_frontend_copy(source, target)
                    else:
                        module.front.unlink_regular(target)
                except OSError:
                    rejected = True
            finally:
                os.open = original_open
            assert swapped and rejected and (outside / 'index.html').read_text() == 'outside sentinel'
            assert stat.S_IMODE(outside.stat().st_mode) == 0o700


def test_concurrent_shared_asset_is_never_overwritten():
    spec = importlib.util.spec_from_file_location('light_deploy', Path(__file__).with_name('overseas-light-deploy.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory(prefix='light-asset-race-') as temporary:
        root = Path(temporary)
        source, target = root / 'source', root / 'shared.js'
        source.write_bytes(b'release')
        original = os.link
        def race(src, dst, *args, **kwargs):
            target.write_bytes(b'concurrent')
            return original(src, dst, *args, **kwargs)
        os.link = race
        try:
            try:
                module.atomic_frontend_copy(source, target, exclusive=True)
            except RuntimeError:
                pass
            else:
                raise AssertionError('concurrent collision was accepted')
        finally:
            os.link = original
        assert target.read_bytes() == b'concurrent'
        assert not list(root.glob('shared.js.overseas-light-*'))

if __name__ == '__main__':
    test_install_preserves_unrelated_directory_and_stale_temp()
    test_missing_asset_directory_is_rejected_without_creation()
    test_parent_swap_cannot_write_or_delete_outside()
    test_concurrent_shared_asset_is_never_overwritten()
    print('ISOLATED_RELEASE_CHECKS_PASS')
