"""A killed first publisher may only recover a proven empty installation."""
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.execution.models import ExecutionGate
from app.modules.domestic_studio.bindings import lock_admission
from app.modules.domestic_studio.models import SkillPublicationAudit
from app.overseas.management import installed_catalog, skill_initialization, skill_objects, skill_publication
from test_domestic_installed_skills import install_fixture


CRASH = '''
import os, sys
from pathlib import Path
from app.overseas.management import skill_objects
root, phase = Path(sys.argv[1]), sys.argv[2]
original = skill_objects.atomic_json
def interrupted(path, value):
    if phase == 'before-manifest' and path.name == 'manifest.json': os._exit(79)
    if phase == 'before-pointer' and path.name == 'current.json': os._exit(79)
    original(path, value)
    if phase == 'after-manifest' and path.name == 'manifest.json': os._exit(79)
skill_objects.atomic_json = interrupted
skill_objects.prepare_release(root, [])
'''

EXISTING_CRASH = '''
import os, sys
from pathlib import Path
from app.overseas.management import installed_catalog, installed_tree, skill_objects
root, source, phase = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
_, old = installed_catalog.read_catalog(root)
if phase == 'release':
    original = skill_objects.atomic_json
    def interrupted(path, value):
        original(path, value)
        if path.name == 'manifest.json': os._exit(79)
    skill_objects.atomic_json = interrupted
    skill_objects.prepare_release(root, old)
else:
    package, entries = installed_tree.tree(source)
    item = {'name': package.name, 'displayName': 'test', 'description': package.description,
            'checksum': package.checksum, 'entries': entries, 'rootName': package.name}
    original = skill_objects.catalog.verify_package
    def interrupted(directory, value, protected=False):
        if directory.name.startswith('.install-') and directory.parent.name == package.name: os._exit(79)
        return original(directory, value, protected)
    skill_objects.catalog.verify_package = interrupted
    skill_objects.prepare_release(root, [item], {package.name: source})
'''


@pytest.mark.parametrize('phase', ['before-manifest', 'after-manifest', 'before-pointer'])
def test_real_process_death_recovers_and_retry_can_publish(tmp_path, phase):
    root = tmp_path / 'skills'
    root.mkdir()
    child = subprocess.run([sys.executable, '-c', CRASH, str(root), phase], check=False)
    assert child.returncode == 79
    assert not (root / 'current.json').exists()
    leftovers = {path.relative_to(root): path.read_bytes() for path in root.rglob('*') if path.is_file()}
    engine = create_engine('sqlite://')
    ExecutionGate.__table__.create(engine)
    with Session(engine) as session:
        session.add(ExecutionGate(id=1))
        session.commit()
        store = SimpleNamespace(installed_root=root, protected=False)
        skill_publication.recover(store, session, audit_model=SkillPublicationAudit, gate=lock_admission)
        release, items = installed_catalog.read_catalog(root)
        assert release == skill_initialization.EMPTY_ID and items == []
        assert skill_objects.prepare_release(root, []) == release
    assert all((root / path).read_bytes() == value for path, value in leftovers.items())
    engine.dispose()


def test_partial_pointer_temporary_is_preserved_during_recovery(tmp_path):
    root = tmp_path / 'skills'
    root.mkdir()
    (root / '.write-abcde123').write_bytes(b'{"release": "')
    assert skill_initialization.recover(root)
    assert installed_catalog.read_catalog(root)[1] == []
    assert (root / '.write-abcde123').read_bytes() == b'{"release": "'


def test_recovery_can_itself_be_interrupted_before_pointer_rename(tmp_path):
    root = tmp_path / 'skills'
    root.mkdir()
    assert subprocess.run([sys.executable, '-c', CRASH, str(root), 'after-manifest'], check=False).returncode == 79
    crash_again = '''
import os, sys
from pathlib import Path
from app.overseas.management import skill_initialization
original = os.replace
def interrupted(source, target):
    if Path(target).name == 'current.json': os._exit(78)
    return original(source, target)
os.replace = interrupted
skill_initialization.recover(Path(sys.argv[1]))
'''
    assert subprocess.run([sys.executable, '-c', crash_again, str(root)], check=False).returncode == 78
    assert not (root / 'current.json').exists()
    assert skill_initialization.recover(root)
    assert installed_catalog.read_catalog(root) == (skill_initialization.EMPTY_ID, [])


@pytest.mark.parametrize('phase', ['release', 'package'])
def test_existing_catalog_keeps_current_and_abandoned_staging_while_retrying(tmp_path, phase):
    root = tmp_path / 'skills'
    root.mkdir()
    install_fixture(tmp_path, root)
    before = installed_catalog.read_catalog(root)
    source = tmp_path / 'replacement' / 'camera-test'
    source.mkdir(parents=True)
    (source / 'SKILL.md').write_text('---\nname: camera-test\ndescription: changed\n---\n# Updated\n', encoding='utf-8')
    child = subprocess.run([sys.executable, '-c', EXISTING_CRASH, str(root), str(source), phase], check=False)
    assert child.returncode == 79
    assert installed_catalog.read_catalog(root) == before
    stages = [path for path in root.rglob('.install-*') if path.is_dir()]
    assert stages
    leftovers = {path.relative_to(root): path.read_bytes() for stage in stages for path in stage.rglob('*') if path.is_file()}
    engine = create_engine('sqlite://')
    ExecutionGate.__table__.create(engine)
    with Session(engine) as session:
        session.add(ExecutionGate(id=1))
        session.commit()
        skill_publication.recover(SimpleNamespace(installed_root=root, protected=False), session,
                                  audit_model=SkillPublicationAudit, gate=lock_admission)
    assert installed_catalog.read_catalog(root) == before
    assert skill_objects.prepare_release(root, before[1]) == before[0]
    assert all(path.exists() for path in stages)
    assert all((root / path).read_bytes() == value for path, value in leftovers.items())
    engine.dispose()


def test_existing_staging_with_hardlink_is_never_reclaimed(tmp_path):
    root = tmp_path / 'skills'
    root.mkdir()
    install_fixture(tmp_path, root)
    stage = root / 'releases' / '.install-abcde123'
    stage.mkdir()
    important = tmp_path / 'important.txt'
    important.write_bytes(b'preserve')
    os.link(important, stage / 'linked')
    skill_publication.recover(SimpleNamespace(installed_root=root, protected=False), None)
    assert important.read_bytes() == b'preserve' and (stage / 'linked').exists()


@pytest.mark.parametrize('unexpected', ['root-file', 'package-tree', 'staging-data', 'foreign-release', 'unknown-temporary'])
def test_unknown_unindexed_content_is_never_deleted_or_treated_as_empty(tmp_path, unexpected):
    root = tmp_path / 'skills'
    root.mkdir()
    if unexpected == 'root-file':
        evidence = root / 'important.txt'
    elif unexpected == 'package-tree':
        evidence = root / 'packages' / 'skill' / 'data'
    elif unexpected == 'staging-data':
        evidence = root / 'releases' / '.install-abcde123' / 'unknown.txt'
    elif unexpected == 'unknown-temporary':
        evidence = root / '.write-abcde123'
    else:
        evidence = root / 'releases' / ('a' * 64) / 'manifest.json'
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_bytes(b'{"beforeBytes": keep this unknown user file' if unexpected == 'unknown-temporary' else b'keep this existing data')
    expected = evidence.read_bytes()
    with pytest.raises(ValueError):
        skill_initialization.recover(root)
    assert evidence.read_bytes() == expected
    assert not (root / 'current.json').exists()
