"""On-disk source graphs exercise the actual manifest and AST boundaries."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import scope_changes as changes
import snapshot


DOMESTIC = 'backend/app/main.py'
OVERSEAS = 'backend/app/overseas/main.py'
HELPER = 'backend/app/modules/files/helper.py'


@pytest.fixture
def releases(tmp_path, monkeypatch):
    monkeypatch.setattr(snapshot, 'RELEASES', tmp_path)
    base = {'backend/' + module.replace('.', '/') + '.py': b'VALUE = 1\n'
            for entries in changes.ENTRYPOINTS.values() for module in entries}
    base.update({'backend/app/__init__.py': b'',
                 'backend/pyproject.toml': b'[project]\n',
                 'backend/uv.lock': b'version = 1\n'})
    u = SimpleNamespace(RELEASE=None)

    def validate():
        manifest = json.loads((u.RELEASE / 'release-manifest.json').read_bytes())
        assert all(snapshot.sha((u.RELEASE / n).read_bytes()) == h
                   for n, h in manifest['files'].items())
    u.validate_release = validate

    def write(name, code):
        root = tmp_path / name
        root.mkdir()
        for n, data in code.items():
            target = root / n
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        hashes = {n: snapshot.sha(data) for n, data in code.items()}
        manifest = {'files': hashes, 'runtime_inputs': {'runtime': 'unchanged'},
                    'provenance': {'source_files': hashes.copy()}}
        (root / 'release-manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        return root

    def check(old, new, scope='domestic', mode='full'):
        return changes.check(u, write('old', old), write('new', new), scope, mode)
    return base, check, write, u


@pytest.mark.parametrize('scope', changes.ENTRYPOINTS)
def test_own_entrypoint_change_allowed(releases, scope):
    base, check, _, _ = releases
    name = 'backend/' + changes.ENTRYPOINTS[scope][0].replace('.', '/') + '.py'
    assert check(base, {**base, name: b'VALUE = 2\n'}, scope) == [name]


def test_cross_domain_import_under_domestic_directory_is_shared(releases):
    base, check, _, _ = releases
    base.update({DOMESTIC: b'from app.modules.files import helper\n',
                 OVERSEAS: b'from app.modules.files.helper import VALUE\n', HELPER: b'VALUE = 1\n'})
    with pytest.raises(RuntimeError, match='shared/joint.*helper.py.*domestic, overseas'):
        check(base, {**base, HELPER: b'VALUE = 2\n'})


def test_old_dependency_still_counts_after_import_removed(releases):
    base, check, _, _ = releases
    base.update({DOMESTIC: b'from app.modules.files import helper\n',
                 OVERSEAS: b'from app.modules.files import helper\n', HELPER: b'VALUE = 1\n'})
    new = {**base, DOMESTIC: b'VALUE = 2\n', HELPER: b'VALUE = 2\n'}
    with pytest.raises(RuntimeError, match='helper.py.*domestic, overseas'):
        check(base, new)


def test_new_dependency_and_old_owner_both_count(releases):
    base, check, _, _ = releases
    base.update({OVERSEAS: b'from app.modules.files import helper\n', HELPER: b'VALUE = 1\n'})
    new = {**base, DOMESTIC: b'from app.modules.files import helper\n', HELPER: b'VALUE = 2\n'}
    with pytest.raises(RuntimeError, match='helper.py.*domestic, overseas'):
        check(base, new)


@pytest.mark.parametrize('delete', [False, True])
def test_exclusive_new_and_deleted_modules(releases, delete):
    base, check, _, _ = releases
    extended = {**base, DOMESTIC: b'from app.modules.files import helper\n', HELPER: b'VALUE = 1\n'}
    old, new = (extended, base) if delete else (base, extended)
    assert check(old, new) == sorted([DOMESTIC, HELPER])


@pytest.mark.parametrize('name', ['backend/app/unreferenced.py', 'backend/template.txt'])
def test_unknown_changes_refused(releases, name):
    base, check, _, _ = releases
    with pytest.raises(RuntimeError, match='unknown ownership'):
        check(base, {**base, name: b'VALUE = 1\n'})


@pytest.mark.parametrize('mode', ['full', 'frontend'])
def test_exclusive_other_business_change_allowed(releases, mode):
    base, check, _, _ = releases
    assert check(base, {**base, OVERSEAS: b'VALUE = 2\n'}, mode=mode) == [OVERSEAS]


@pytest.mark.parametrize('mode', ['full', 'frontend'])
def test_shared_service_change_cannot_piggyback_business_release(releases, mode):
    base, check, _, _ = releases
    with pytest.raises(RuntimeError, match='shared/joint.*identity/main.py.*shared'):
        check(base, {**base, 'backend/app/identity/main.py': b'VALUE = 2\n'}, mode=mode)


@pytest.mark.parametrize('reverse', [False, True])
def test_foreign_ownership_must_be_known_in_every_existing_version(releases, reverse):
    base, check, _, _ = releases
    base[HELPER] = b'VALUE = 1\n'
    new = {**base, OVERSEAS: b'from app.modules.files import helper\n', HELPER: b'VALUE = 2\n'}
    old, new = (new, base) if reverse else (base, new)
    with pytest.raises(RuntimeError, match='helper.py.*unknown ownership'):
        check(old, new)


@pytest.mark.parametrize('delete', [False, True])
def test_exclusive_foreign_new_and_deleted_modules(releases, delete):
    base, check, _, _ = releases
    extended = {**base, OVERSEAS: b'from app.modules.files import helper\n', HELPER: b'VALUE = 1\n'}
    old, new = (extended, base) if delete else (base, extended)
    assert check(old, new, mode='frontend') == sorted([OVERSEAS, HELPER])


def test_shared_scope_cannot_bypass_common_dependency(releases):
    base, check, _, _ = releases
    entry = 'backend/app/identity/main.py'
    base.update({DOMESTIC: b'import app.core.config\n', OVERSEAS: b'import app.core.config\n',
                 entry: b'import app.core.config\n', 'backend/app/core/config.py': b'VALUE = 1\n'})
    with pytest.raises(RuntimeError, match='config.py.*domestic, overseas, shared'):
        check(base, {**base, 'backend/app/core/config.py': b'VALUE = 2\n'}, 'shared')


def test_package_init_and_relative_imports_are_dependencies(releases):
    base, check, _, _ = releases
    init = 'backend/app/modules/files/__init__.py'
    base.update({DOMESTIC: b'from app.modules import files\n', init: b'from . import helper\n',
                 OVERSEAS: b'from app.modules.files.helper import VALUE\n', HELPER: b'VALUE = 1\n'})
    with pytest.raises(RuntimeError, match='helper.py.*domestic, overseas'):
        check(base, {**base, HELPER: b'VALUE = 2\n'})


def test_celery_string_modules_are_dependencies(releases):
    base, check, _, _ = releases
    base.update({DOMESTIC: b'from celery import Celery\napp = Celery(include=["app.modules.files.helper"])\n',
                 OVERSEAS: b'from app.modules.files import helper\n', HELPER: b'VALUE = 1\n'})
    with pytest.raises(RuntimeError, match='helper.py.*domestic, overseas'):
        check(base, {**base, HELPER: b'VALUE = 2\n'})


@pytest.mark.parametrize('loader', [b'import importlib\nimportlib.import_module(NAME)\n',
                                    b'__import__(NAME)\n', b'exec(SOURCE)\n', b'import runpy\n',
                                    b'from builtins import __import__ as load\nload(NAME)\n',
                                    b'celery_app.autodiscover_tasks(PACKAGES)\n'])
def test_unknown_dynamic_import_fails_closed(releases, loader):
    base, check, _, _ = releases
    base[OVERSEAS] = loader
    with pytest.raises(RuntimeError, match='Dynamic Python'):
        check(base, {**base, DOMESTIC: b'VALUE = 2\n'})


def test_frontend_refuses_target_backend_change(releases):
    base, check, _, _ = releases
    with pytest.raises(RuntimeError, match='Frontend-only'):
        check(base, {**base, DOMESTIC: b'VALUE = 2\n', OVERSEAS: b'VALUE = 2\n'}, mode='frontend')


@pytest.mark.parametrize('name', ['backend/entrypoint.sh', 'backend/app/unreferenced.py'])
def test_frontend_refuses_unknown_backend_change(releases, name):
    base, check, _, _ = releases
    with pytest.raises(RuntimeError, match='unknown ownership'):
        check(base, {**base, name: b'VALUE = 2\n'}, mode='frontend')


def test_frontend_source_provenance_changes_do_not_require_same_commit(releases):
    base, _, write, u = releases
    old, new = write('old', base), write('new', base)
    manifest_path = new / 'release-manifest.json'
    m = json.loads(manifest_path.read_bytes())
    m.update(commit='new')
    m['provenance']['source_files']['frontend/src/App.tsx'] = 'new frontend hash'
    manifest_path.write_text(json.dumps(m), encoding='utf-8')
    assert changes.check(u, old, new, 'domestic', 'frontend') == []


@pytest.mark.parametrize('name', ['backend/pyproject.toml', 'backend/uv.lock',
                                 'backend/migrations/new_revision.py'])
def test_dependency_and_schema_changes_use_snapshot_guard(releases, name):
    base, check, _, _ = releases
    with pytest.raises(RuntimeError, match='Dependency/schema'):
        check(base, {**base, name: b'changed\n'})


def test_incomplete_provenance_rejected(releases):
    base, _, write, u = releases
    old, new = write('old', base), write('new', {**base, DOMESTIC: b'VALUE = 2\n'})
    path = new / 'release-manifest.json'
    m = json.loads(path.read_bytes())
    del m['provenance']['source_files'][DOMESTIC]
    path.write_text(json.dumps(m), encoding='utf-8')
    with pytest.raises(RuntimeError, match='Incomplete backend'):
        changes.check(u, old, new, 'domestic', 'full')


def test_real_repository_graph_confirms_cross_domain_file_helpers():
    root = Path(__file__).resolve().parents[3] / 'hengxin-smart-image'
    code = {p.relative_to(root).as_posix(): p.read_bytes()
            for p in (root / 'backend/app').rglob('*.py') if '__pycache__' not in p.parts}
    owners = changes.Imports(code).owners()
    assert owners['backend/app/modules/files/validation.py'] == {'domestic', 'overseas'}
    assert owners['backend/app/core/config.py'] == {'domestic', 'overseas', 'shared'}
    assert owners['backend/app/execution/credential_broker.py'] == {'shared'}
