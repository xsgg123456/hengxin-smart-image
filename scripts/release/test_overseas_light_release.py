"""Package integrity and fail-closed rollback without production access."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import pytest


def module(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), Path(__file__).with_name(name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def test_public_svg_uses_canonical_line_endings_but_hashed_assets_do_not():
    package = module('overseas-light-package')
    body = b'<svg>\r\n<path/>\r\n</svg>\r\n'
    expected = b'<svg>\n<path/>\n</svg>\n'
    assert package.asset_bytes('frontend/dist/favicon.svg', body) == expected
    assert package.asset_bytes('frontend/dist/samples/product-0.svg', body) == expected
    assert package.asset_bytes('frontend/dist/assets/icon-Ab12.svg', body) == body
    assert package.asset_bytes('frontend/dist/image.png', body) == body


def test_preflight_fails_on_existing_asset_collision(tmp_path):
    deploy = module('overseas-light-deploy')
    source, app = tmp_path / 'source', tmp_path / 'app'
    for root in (source, app):
        (root / 'frontend/dist').mkdir(parents=True)
        (root / 'frontend/dist/icon.svg').write_bytes(b'same')
    deploy.check_frontend_collisions(source, app)
    (app / 'frontend/dist/icon.svg').write_bytes(b'other')
    with pytest.raises(RuntimeError, match='Existing shared asset collision: icon.svg'):
        deploy.check_frontend_collisions(source, app)


def test_preflight_rejects_non_directory_and_linked_asset_paths(tmp_path, monkeypatch):
    deploy = module('overseas-light-deploy')
    source, app = tmp_path / 'source', tmp_path / 'app'
    (source / 'frontend/dist/samples').mkdir(parents=True)
    (source / 'frontend/dist/samples/icon.svg').write_bytes(b'icon')
    (app / 'frontend/dist').mkdir(parents=True)
    parent = app / 'frontend/dist/samples'
    parent.write_text('not a directory')
    with pytest.raises(RuntimeError, match='Unsafe shared asset directory: samples'):
        deploy.check_frontend_collisions(source, app)
    parent.unlink()
    original = Path.is_symlink
    monkeypatch.setattr(Path, 'is_symlink', lambda p: p == parent or original(p))
    with pytest.raises(RuntimeError, match='Unsafe shared asset directory: samples'):
        deploy.check_frontend_collisions(source, app)
    parent.mkdir()
    linked = parent / 'icon.svg'
    linked.write_bytes(b'icon')
    monkeypatch.setattr(Path, 'is_symlink', lambda p: p == linked or original(p))
    with pytest.raises(RuntimeError, match='Linked shared asset: samples/icon.svg'):
        deploy.check_frontend_collisions(source, app)
    monkeypatch.setattr(Path, 'is_symlink', original)
    (app / 'frontend/dist/index.html').mkdir()
    with pytest.raises(RuntimeError, match='Unsafe frontend entry: frontend/dist/index.html'):
        deploy.check_frontend_collisions(source, app)
    with pytest.raises(RuntimeError, match='Unsafe asset directory'):
        deploy.front.require_asset_directory(app / 'frontend/dist', app / 'frontend/dist/../outside')


def test_conflicting_asset_aborts_prepare_and_deploy_before_traffic_changes(tmp_path, monkeypatch):
    deploy = module('overseas-light-deploy')
    source, app, work = tmp_path / 'source', tmp_path / 'app', tmp_path / 'work'
    for root in (source, app):
        (root / 'frontend/dist').mkdir(parents=True)
    (source / 'frontend/dist/icon.svg').write_bytes(b'new')
    (app / 'frontend/dist/icon.svg').write_bytes(b'old')
    work.mkdir()
    overlay = work / 'old-overlay.json'
    overlay.write_text('original')
    data = {'oldId': 'old', 'oldImage': 'old-image', 'image': 'new-image', 'compose': {},
            'protected': {}, 'manifest': 'm', 'oldOverlayHash': deploy.r.digest(overlay)}
    events = []
    monkeypatch.setattr(deploy.r.a, 'APP', app)
    monkeypatch.setattr(deploy.gate, 'set_gate', lambda *_args: events.append('gate'))
    monkeypatch.setattr(deploy.r.a, 'compose', lambda *_args, **_kwargs: events.append('compose'))
    monkeypatch.setattr(deploy.r, 'inspect', lambda: {'Id': 'old', 'Image': 'old-image', 'State': {'Running': True}})
    monkeypatch.setattr(deploy.r, 'verify_package', lambda *_args: {'api': {'image': 'old-image',
        'files': {'one.py': {'baseline': 'baseline'}}}})
    monkeypatch.setattr(deploy.r, 'hashes', lambda *_args: {'one.py': 'baseline'})
    monkeypatch.setattr(deploy.r.b, 'snapshot', lambda: {'frontendVersion': '0.2.66'})
    with pytest.raises(RuntimeError, match='Existing shared asset collision'):
        deploy.prepare(work, source)
    monkeypatch.setattr(deploy, 'state', lambda *_args, **_kwargs: (data, source))
    with pytest.raises(RuntimeError, match='Existing shared asset collision'):
        deploy.deploy(work)
    assert events == [] and not (work / 'SWITCH_STARTED').exists()


def test_unique_atomic_copy_ignores_legacy_temp_and_cleans_up_on_failure(tmp_path, monkeypatch):
    deploy = module('overseas-light-deploy')
    source, target = tmp_path / 'source', tmp_path / 'index.html'
    source.write_bytes(b'new')
    target.write_bytes(b'old')
    stale = tmp_path / 'index.html.sku-new'
    stale.write_bytes(b'leave intact')
    deploy.atomic_frontend_copy(source, target)
    assert target.read_bytes() == b'new' and stale.read_bytes() == b'leave intact'
    assert not list(tmp_path.glob('index.html.overseas-light-*'))
    monkeypatch.setattr(deploy.os, 'replace', lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError('replace failed')))
    with pytest.raises(OSError, match='replace failed'):
        deploy.atomic_frontend_copy(source, target)
    assert target.read_bytes() == b'new' and stale.read_bytes() == b'leave intact'
    assert not list(tmp_path.glob('index.html.overseas-light-*'))


def test_shared_asset_created_concurrently_is_never_overwritten(tmp_path, monkeypatch):
    deploy = module('overseas-light-deploy')
    source, target = tmp_path / 'source', tmp_path / 'shared.js'
    source.write_bytes(b'release')
    link = os.link
    def race(src, dst, *args, **kwargs):
        target.write_bytes(b'concurrent')
        return link(src, dst, *args, **kwargs)
    monkeypatch.setattr(os, 'link', race)
    with pytest.raises(RuntimeError, match='Existing shared asset collision'):
        deploy.atomic_frontend_copy(source, target, exclusive=True)
    assert target.read_bytes() == b'concurrent'
    assert not list(tmp_path.glob('shared.js.overseas-light-*'))


def test_install_never_chmods_unrelated_old_directory(tmp_path, monkeypatch):
    deploy = module('overseas-light-deploy')
    source, app, backup = tmp_path / 'source', tmp_path / 'app', tmp_path / 'backup'
    (source / 'frontend/dist/assets').mkdir(parents=True)
    (source / 'frontend/dist/index.html').write_text('new index')
    (source / 'frontend/dist/assets/new.js').write_text('new asset')
    (source / 'frontend/package.json').write_text('{"version":"0.2.67"}')
    (source / 'release.json').write_text('{}')
    (app / 'frontend/dist/private').mkdir(parents=True)
    (app / 'frontend/dist/assets').mkdir()
    (app / 'frontend/dist/index.html').write_text('old index')
    (app / 'frontend/package.json').write_text('{"version":"0.2.66"}')
    private = app / 'frontend/dist/private'
    before = private.stat()
    chmodded, fchmodded = [], []
    chmod = Path.chmod
    monkeypatch.setattr(Path, 'chmod', lambda p, mode: (chmodded.append(p), chmod(p, mode))[1])
    if hasattr(os, 'fchmod'):
        fchmod = os.fchmod
        def capture_fchmod(descriptor, mode):
            value = os.fstat(descriptor)
            fchmodded.append((value.st_dev, value.st_ino))
            return fchmod(descriptor, mode)
        monkeypatch.setattr(os, 'fchmod', capture_fchmod)

    files = {name: deploy.r.digest(source / name) for name in (
        'frontend/dist/index.html', 'frontend/dist/assets/new.js', 'frontend/package.json')}
    monkeypatch.setattr(deploy.r, 'verify_package', lambda *_args: {'files': files})
    work = tmp_path / 'work'
    work.mkdir(mode=0o700)
    with deploy.front.protect_publication_directories(app, work):
        deploy.install_frontend(source, app, backup)
    after = private.stat()
    assert private not in chmodded and (before.st_dev, before.st_ino) not in fchmodded
    assert (after.st_dev, after.st_ino, after.st_mode) == (before.st_dev, before.st_ino, before.st_mode)
    assert (app / 'frontend/dist/assets/new.js').is_file()
    assert (app / 'frontend/dist/index.html').read_text() == 'new index'
    assert (backup / 'COMPLETE.json').is_file()


def test_package_rejects_changed_or_extra_source(tmp_path):
    scope = module('overseas-light-runtime')
    files = {('api/' + name): b'code\n' for name in scope.r.FILES}
    files.update({('tests/' + name): b'test\n' for name in ('conftest.py', *scope.TESTS)})
    files.update({('scripts/release/' + name + '.py'): b'helper\n' for name in scope.HELPERS})
    files.update({'frontend/package.json': b'{"version":"0.2.67"}',
                  'frontend/dist/index.html': b'<script type="module" src="/assets/app.js"></script>',
                  'frontend/dist/assets/app.js': b'console.log(1)'})
    sha = lambda raw: hashlib.sha256(raw).hexdigest()
    manifest = {'release': 'overseas-light-20261107-abcdef0', 'version': '0.2.67', 'commit': 'a' * 40,
                'candidateId': 'b' * 64, 'api': {'image': scope.BASE_IMAGE,
                'files': {n: {'baseline': 'c' * 64, 'sha256': sha(files['api/' + n])} for n in scope.r.FILES}},
                'files': {n: sha(body) for n, body in files.items()}}
    for name, body in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
    (tmp_path / 'release.json').write_text(json.dumps(manifest))
    assert scope.verify_package(tmp_path) == manifest
    first = tmp_path / ('api/' + next(iter(scope.r.FILES)))
    first.write_bytes(b'tampered')
    with pytest.raises(RuntimeError, match='checksum'):
        scope.verify_package(tmp_path)
    first.write_bytes(b'code\n')
    (tmp_path / 'extra').write_text('unexpected')
    with pytest.raises(RuntimeError, match='Unmanifested'):
        scope.verify_package(tmp_path)
    (tmp_path / 'extra').unlink()
    (tmp_path / 'frontend/dist/index.html').write_text('html')
    manifest['files']['frontend/dist/index.html'] = sha(b'html')
    (tmp_path / 'release.json').write_text(json.dumps(manifest))
    with pytest.raises(RuntimeError, match='entry missing JavaScript'):
        scope.verify_package(tmp_path)
