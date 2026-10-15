"""Exercise frozen Skill prompt construction without a database or paid CLI."""
import json
from types import SimpleNamespace

import pytest

from app.overseas.execution import materials
from app.overseas.management import installed_catalog
from app.overseas.studio import execution


PERSONA = '你是设计师的协作助手，按设计师的要求提供帮助。'
ORIGINAL = '  设计产品\n保留原文、空格与 $literal  '


def prepare(tmp_path, monkeypatch, name, previous=None, attachment=False):
    work, control = tmp_path / 'work', tmp_path / 'control'
    work.mkdir(parents=True)
    control.mkdir()
    workspace = SimpleNamespace(work=work, control=control, previous_session=previous,
                                skill_name='stale-selection')
    skill = None if name is None else {
        'name': name, 'displayName': '中文展示名称',
        'files': {'SKILL.md': f'---\nname: {name}\ndescription: Test skill\n---\nTest.'}}
    inputs = [dict(name='设计参考.PNG')] if attachment else []
    job = SimpleNamespace(payload=dict(text=ORIGINAL, skill=skill, inputs=inputs))
    monkeypatch.setattr(execution, 'get_store', lambda: None)
    monkeypatch.setattr(execution, 'read', lambda store, source: b'original attachment')
    materials.prepare(job, workspace)
    return job, workspace


@pytest.mark.parametrize('previous', [None, 'existing-session'])
@pytest.mark.parametrize('name', [None, 'amazon-new-product-aplus'])
@pytest.mark.parametrize('attachment', [False, True])
def test_selected_skill_prompt_preserves_text_persona_and_attachments(
        tmp_path, monkeypatch, previous, name, attachment):
    job, workspace = prepare(tmp_path, monkeypatch, name, previous, attachment)
    prompt = execution.HANDLER.prepare(job, workspace)
    expected = [] if previous else [PERSONA]
    if name:
        expected.append('$' + name)
        assert (workspace.local_skill / 'SKILL.md').is_file()
    expected.append(ORIGINAL)
    if attachment:
        expected.append('附件文件：' + json.dumps(
            [dict(name='设计参考.PNG', path='/work/inputs/1.png')], ensure_ascii=False))
        assert (workspace.work / 'inputs/1.png').read_bytes() == b'original attachment'
    assert prompt == '\n\n'.join(expected)
    assert 'Skill文件：' not in prompt
    assert '中文展示名称' not in prompt
    assert '$stale-selection' not in prompt


def test_switch_and_deselect_use_only_current_round_skill(tmp_path, monkeypatch):
    for index, name in enumerate(['first-skill', 'second-skill', None]):
        job, workspace = prepare(tmp_path / str(index), monkeypatch, name,
                                 previous='same-session')
        expected = '$' + name + '\n\n' + ORIGINAL if name else ORIGINAL
        assert execution.HANDLER.prepare(job, workspace) == expected


def test_installed_skill_uses_verified_package_name(tmp_path, monkeypatch):
    job, workspace = prepare(tmp_path, monkeypatch, None, previous='same-session')
    job.payload['skill'] = dict(installedRelease='frozen-release', name='payload-name',
                                displayName='中文展示名称')
    package = SimpleNamespace(name='verified-declaration', files={
        'SKILL.md': b'---\nname: verified-declaration\ndescription: Test\n---\nTest.'})
    verified = []

    def frozen_package(skill):
        verified.append(skill)
        return package

    monkeypatch.setattr(installed_catalog, 'frozen_package', frozen_package)
    materials.prepare(job, workspace)
    assert verified == [job.payload['skill']]
    assert execution.HANDLER.prepare(job, workspace) == '$verified-declaration\n\n' + ORIGINAL
    assert workspace.local_skill.name == 'verified-declaration'
    assert (workspace.local_skill / 'SKILL.md').read_bytes() == package.files['SKILL.md']
