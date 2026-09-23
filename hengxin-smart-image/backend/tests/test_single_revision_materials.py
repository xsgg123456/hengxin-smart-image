import hashlib
import pytest
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


@pytest.mark.parametrize('mode', ['text', 'wallpaper'])
def test_fourth_slot_uses_historical_unmarked_base_and_current_annotation(task_env, tmp_path, monkeypatch, mode):
    data = body(task_env, mode)
    if mode == 'text':
        data['sources'] *= 4
    else:
        response = task_env[0].post('/api/v1/templates', json=dict(name='四张底图', mode=mode,
            images=data['sources'] * 4, skillVersionId=data['skillVersionId'], active=True, notes='冻结'))
        assert response.status_code == 200, response.text
        template = response.json()
        data.update(templateId=template['id'], templateVersion=template['version'])
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
    assert '/work/current/00.png' in prompt
    assert 'Skill' not in prompt and '使用 $' not in prompt
    if mode == 'wallpaper':
        assert '只展示并提供修改后的这1张成品图片' in prompt
        assert '截图界面不得进入成品' in prompt
        assert target['originalPath'] == '/work/original/00.png'
        assert len(list((work / 'original').iterdir())) == 1
    else:
        assert '只交付修改后的这 1 张图片' in prompt and '底图' not in prompt
        assert '标注内容不要出现在成品中' in prompt
        assert not list((work / 'targets').iterdir())
    assert '/work/annotation/reference.png' in prompt and '只改圈内镜头' in prompt
    assert 'skillPath' not in manifest and 'path' not in target
    assert not (work / 'skills').exists()


def test_text_single_revision_does_not_read_any_original_images(task_env, tmp_path, monkeypatch):
    from app.modules.tasks.models import TaskSource
    data = body(task_env, 'text')
    data['sources'].append(upload(task_env[0]).json())
    receipt = frozen_request(task_env, data)
    run_generation(job_for(task_env[1], receipt), task_env[1], task_env[2])
    accepted = revise(task_env, receipt, target=1).json()
    with task_env[1]() as session:
        sources = session.scalars(select(TaskSource).where(TaskSource.task_id == UUID(receipt['taskId'])))
        for source in sources:
            file = session.get(FileRecord, source.file_id)
            task_env[2].objects[file.object_key] = b'broken original'
    manifest, work = prepared(task_env, accepted, tmp_path, monkeypatch)
    assert manifest['inputs'] == []
    assert manifest['targets'][0]['currentPath'] == '/work/current/00.png'
    assert not list((work / 'inputs').iterdir()) and not list((work / 'targets').iterdir())
    assert 'skillPath' not in manifest


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


@pytest.mark.parametrize('source_type', ['zip', 'local'])
def test_wallpaper_revision_reads_original_but_not_skill(task_env, tmp_path, monkeypatch, source_type):
    from app.modules.skills.models import SkillVersionRecord
    monkeypatch.setattr(ObjectStream, 'read', lambda self, size: self.data[:size], raising=False)
    data = body(task_env, 'wallpaper')
    data['sources'] = [upload(task_env[0]).json()]
    receipt = frozen_request(task_env, data)
    run_generation(job_for(task_env[1], receipt), task_env[1], task_env[2])
    accepted = revise(task_env, receipt, target=0).json()
    with task_env[1].begin() as session:
        task = session.get(TaskRecord, UUID(receipt['taskId']))
        original = session.get(FileRecord, UUID(task.template_snapshot['images'][0]['fileId']))
        original_bytes = task_env[2].objects[original.object_key]
        skill = session.get(SkillVersionRecord, task.skill_version_id)
        task_env[2].objects[skill.object_key] = b'broken skill'
        skill.source_type = source_type
    def unavailable(*args):
        raise AssertionError('single revision must not validate Skill')
    monkeypatch.setattr('app.worker.skill_check.validate_local', unavailable)
    work = tmp_path / 'single'
    work.mkdir()
    workspace = Workspace(tmp_path / 'home', work, tmp_path / 'control')
    with task_env[1]() as session:
        manifest = prepare_materials(session, task_env[2],
            session.get(TaskRecord, UUID(receipt['taskId'])),
            session.get(RoundRecord, UUID(accepted['roundId'])), workspace)
    assert workspace.use_skill is False
    assert 'skillPath' not in manifest and 'path' not in manifest['targets'][0]
    assert (work / 'current/00.png').exists() and (work / 'inputs/00.png').exists()
    assert manifest['targets'][0]['originalPath'] == '/work/original/00.png'
    assert (work / 'original/00.png').read_bytes() == original_bytes
    assert not (work / 'targets').exists() and not (work / 'skills').exists()


@pytest.mark.parametrize('problem', ['deleted', 'corrupt', 'missing'])
def test_wallpaper_revision_cannot_omit_unavailable_original(task_env, tmp_path, monkeypatch, problem):
    from app.models import utcnow
    data = body(task_env, 'wallpaper')
    data['sources'] = [upload(task_env[0], repaired_image_bytes()).json()]
    receipt = frozen_request(task_env, data)
    run_generation(job_for(task_env[1], receipt), task_env[1], task_env[2])
    accepted = revise(task_env, receipt, target=1).json()
    with task_env[1].begin() as session:
        task = session.get(TaskRecord, UUID(receipt['taskId']))
        original = session.get(FileRecord, UUID(task.template_snapshot['images'][1]['fileId']))
        if problem == 'deleted':
            original.deleted_at = utcnow()
        elif problem == 'corrupt':
            task_env[2].objects[original.object_key] = b'broken'
        else:
            del task_env[2].objects[original.object_key]
    with pytest.raises((ValueError, KeyError)) as caught:
        prepared(task_env, accepted, tmp_path, monkeypatch)
    if problem == 'deleted':
        assert str(caught.value) == '对应原始底图不可用'


def test_wallpaper_original_uses_frozen_template_slot(task_env, tmp_path, monkeypatch):
    from app.modules.templates.models import TemplateVersionRecord
    data = body(task_env, 'wallpaper')
    different = upload(task_env[0], repaired_image_bytes()).json()
    template = task_env[0].post('/api/v1/templates', json=dict(name='不同底图', mode='wallpaper',
        images=[data['sources'][0], different], skillVersionId=data['skillVersionId'],
        active=True, notes='原版')).json()
    data.update(templateId=template['id'], templateVersion=template['version'])
    receipt = frozen_request(task_env, data)
    run_generation(job_for(task_env[1], receipt), task_env[1], task_env[2])
    accepted = revise(task_env, receipt, target=1).json()
    # Even if the live template data changes, the task's frozen mapping wins.
    with task_env[1].begin() as session:
        version = session.scalar(select(TemplateVersionRecord).where(
            TemplateVersionRecord.template_id == UUID(template['id'])))
        version.images = [data['sources'][0], data['sources'][0]]
    manifest, work = prepared(task_env, accepted, tmp_path, monkeypatch)
    assert manifest['targets'][0]['taskSlot'] == 1
    assert (work / 'original/00.png').read_bytes() == repaired_image_bytes()
    assert (work / 'original/00.png').read_bytes() != (work / 'inputs/00.png').read_bytes()
