from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import select

from files_helpers import files_env
from test_codex_runner import real_env, frozen_request
from app.execution.materials import prepare_materials, SkillDeploymentError
from app.execution.workspace import prepare_workspace
from app.core.config import get_settings
from app.modules.skills.local_tree import LocalTree
from app.modules.skills.models import SkillVersionRecord
from app.modules.tasks.models import TaskRecord, RoundRecord
from app.resource_models import UserRecord


def test_local_materials_mount_frozen_version_without_reading_zip_or_copying(real_env, monkeypatch):
    import app.worker.skill_check as checker
    client, factory, store, identity = real_env
    receipt = frozen_request(real_env)
    checked = []
    published = Path('/published/frozen/1.0.0')
    def validate(record, expected):
        checked.append((str(record.id), expected))
        assert record.status == 'disabled'  # Old tasks remain bound when disabled.
        return LocalTree(published, expected, {}, {})
    monkeypatch.setattr(checker, 'validate_local', validate)
    with factory.begin() as session:
        task = session.get(TaskRecord, UUID(receipt['taskId']))
        skill = session.get(SkillVersionRecord, task.skill_version_id)
        skill.source_type, skill.status = 'local', 'disabled'
        skill.bucket = skill.object_key = None
        session.get(UserRecord, identity[0]).role = 'super_admin'
    with factory() as session:
        task = session.get(TaskRecord, UUID(receipt['taskId']))
        round = session.get(RoundRecord, UUID(receipt['roundId']))
        settings = get_settings()
        workspace = prepare_workspace(settings.codex_execution_root, task.id, round.id, settings.codex_auth_file)
        manifest = prepare_materials(session, store, task, round, workspace)
        assert manifest['inputs'] and workspace.local_skill == published
        assert not (workspace.work / 'skills').exists()
        assert manifest['skillPath'] == workspace.skill_path + '/SKILL.md'
        assert checked == [(str(task.skill_version_id), task.skill_snapshot['checksum'])]
    assert client.delete(f'/api/v1/management/skills/{checked[0][0]}').status_code == 409


def test_frozen_local_checksum_must_exist_and_match(real_env):
    from app.worker.skill_check import validate_local
    receipt = frozen_request(real_env)
    with real_env[1]() as session:
        version = session.scalar(select(SkillVersionRecord))
        with pytest.raises(ValueError, match='冻结版本'):
            validate_local(version, '')
        with pytest.raises(ValueError, match='冻结版本'):
            validate_local(version, 'wrong')


def test_legacy_zip_uses_safe_named_directory_and_preserves_entire_package(real_env):
    import hashlib
    from io import BytesIO
    from zipfile import ZipFile
    receipt = frozen_request(real_env)
    buffer = BytesIO()
    with ZipFile(buffer, 'w') as archive:
        for name, content in {'SKILL.md': '---\nname: test\ndescription: demo\n---\n',
                              'scripts/edit.py': '# script', 'references/rules.txt': 'rules',
                              'assets/example.txt': 'asset'}.items():
            archive.writestr(name, content)
    raw = buffer.getvalue()
    with real_env[1].begin() as session:
        task = session.get(TaskRecord, UUID(receipt['taskId']))
        version = session.get(SkillVersionRecord, task.skill_version_id)
        version.skill.name = '../旧名称'
        version.checksum = hashlib.sha256(raw).hexdigest()
        task.skill_snapshot = {**task.skill_snapshot, 'checksum': version.checksum}
        real_env[2].objects[version.object_key] = raw
    with real_env[1]() as session:
        task = session.get(TaskRecord, UUID(receipt['taskId']))
        round = session.get(RoundRecord, UUID(receipt['roundId']))
        settings = get_settings()
        workspace = prepare_workspace(settings.codex_execution_root, task.id, round.id, settings.codex_auth_file)
        manifest = prepare_materials(session, real_env[2], task, round, workspace)
        assert manifest['skillPath'] == f'/work/skills/legacy-{task.skill_version_id}/SKILL.md'
        folder = workspace.work / 'skills' / workspace.skill_name
        for name in ('SKILL.md', 'scripts/edit.py', 'references/rules.txt', 'assets/example.txt'):
            assert (folder / name).is_file()
