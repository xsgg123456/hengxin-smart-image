import hashlib
from uuid import UUID

from app.execution.fixture_runner import run_generation
from app.execution.materials import prepare_materials
from app.execution.prompts import prompt_for
from app.execution.workspace import Workspace
from app.modules.tasks.models import RoundRecord, TaskRecord, ResultSlotRecord
from app.resource_models import FileRecord
from sqlalchemy import select
from files_helpers import files_env, ObjectStream  # noqa: F401
from test_codex_runner import frozen_request, repaired_image_bytes
from test_files import upload
from test_revisions import detail, revise
from test_tasks import task_env, body, job_for  # noqa: F401


def prepared(env, receipt, tmp_path, monkeypatch):
    monkeypatch.setattr(ObjectStream, 'read', lambda self, size: self.data[:size], raising=False)
    work = tmp_path / receipt['roundId']
    work.mkdir()
    workspace = Workspace(tmp_path / 'home', work, tmp_path / 'control')
    with env[1]() as session:
        task = session.get(TaskRecord, UUID(receipt['taskId']))
        round = session.get(RoundRecord, UUID(receipt['roundId']))
        manifest = prepare_materials(session, env[2], task, round, workspace)
    return manifest, work


def test_fourth_slot_uses_historical_unmarked_base_and_current_annotation(task_env, tmp_path, monkeypatch):
    data = body(task_env)
    data['sources'] *= 4
    receipt = frozen_request(task_env, data)
    run_generation(job_for(task_env[1], receipt), task_env[1], task_env[2])
    before = detail(task_env, receipt)
    version = before['slots'][3]['versions'][0]
    base = version['id']
    v2 = revise(task_env, receipt, target=3, baseVersionId=base).json()
    run_generation(job_for(task_env[1], v2), task_env[1], task_env[2])
    latest = detail(task_env, receipt)['slots'][3]['versions'][-1]
    # Different bytes prove selection, not merely a version label in the manifest.
    with task_env[1].begin() as session:
        file = session.get(FileRecord, UUID(latest['fileId']))
        replacement = repaired_image_bytes()
        task_env[2].objects[file.object_key] = replacement
        file.checksum, file.size_bytes = hashlib.sha256(replacement).hexdigest(), len(replacement)
    annotation = upload(task_env[0]).json()
    accepted = revise(task_env, receipt, key='history', target=3, baseVersionId=base,
                      annotationFileId=annotation['fileId']).json()
    manifest, work = prepared(task_env, accepted, tmp_path, monkeypatch)
    target = manifest['targets'][0]
    assert target['slot'] == 0 and target['taskSlot'] == 3
    assert target['baseVersionId'] == base and target['currentVersion'] == 1
    assert (work / 'current/00.png').read_bytes() == task_env[0].get(version['url']).content
    assert (work / 'current/00.png').read_bytes() != task_env[0].get(latest['url']).content
    assert (work / 'annotation/reference.png').read_bytes() == task_env[0].get(annotation['url']).content
    prompt = prompt_for(manifest, '只改圈内镜头', 'original-session')
    assert '第 4 张底图的本轮基础版本 V1' in prompt and '第 1 张底图' not in prompt
    assert '只修改并交付上述目标 1 张' in prompt and '4 张输入/交付要求' in prompt
    assert '不得复制到成品' in prompt and '不猜测修改区域' in prompt
    assert '/work/annotation/reference.png' in prompt and '只改圈内镜头' in prompt


def test_explicit_empty_base_stays_empty_and_legacy_round_uses_current(task_env, tmp_path, monkeypatch):
    receipt = frozen_request(task_env)
    run_generation(job_for(task_env[1], receipt), task_env[1], task_env[2])
    # Simulate a frozen no-result revision whose slot later has a result; material
    # selection must still honor null, while pre-migration rounds retain fallback.
    with task_env[1].begin() as session:
        round = session.get(RoundRecord, UUID(receipt['roundId']))
        round.target = 0
        round.execution_config = {**round.execution_config, 'singleInputFrozen': True}
    manifest, _ = prepared(task_env, receipt, tmp_path, monkeypatch)
    assert 'currentPath' not in manifest['targets'][0]
    with task_env[1].begin() as session:
        round = session.get(RoundRecord, UUID(receipt['roundId']))
        round.execution_config = {}
    legacy = tmp_path / 'legacy'
    legacy.mkdir()
    manifest, _ = prepared(task_env, receipt, legacy, monkeypatch)
    assert manifest['targets'][0]['currentVersion'] == 1
