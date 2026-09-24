import json
from pathlib import Path

import pytest

from app.image_revision_prompt import ANNOTATION_GUIDANCE, build_revision_prompt
from app.execution.prompts import prompt_for, wallpaper_revision_prompt


@pytest.mark.parametrize('annotation', [None, '图4'])
@pytest.mark.parametrize('note', ['恢复边框，保留新壁纸。', '包含"引号"\n和换行'])
def test_api_reference_roles_and_unmodified_note(annotation, note):
    prompt = build_revision_prompt(current='图1', original='图2', materials=['图3'],
                                   annotation=annotation, note=note, api=True)
    assert prompt.index('图1') < prompt.index('图2') < prompt.index('图3')
    assert ('图4' in prompt) == bool(annotation)
    assert ('问题位置参考图：' in prompt) == bool(annotation)
    assert json.dumps(note, ensure_ascii=False) in prompt
    assert '共用参考素材' in prompt and '唯一修改对象' in prompt
    assert '不输出对比图、拼图或参考图' in prompt
    assert '画布尺寸' not in prompt and '/work/' not in prompt


def test_annotation_only_has_explicit_instruction():
    prompt = build_revision_prompt(current='图1', original='图2', materials=['图3'],
                                   annotation='图4', note='', api=True)
    assert '请结合图4的标注定位问题' in prompt
    assert '圈线、箭头、文字标记及截图界面不得进入成品' in prompt


@pytest.mark.parametrize('case', json.loads(
    (Path(__file__).parent / 'fixtures/cli_revision_briefs.json').read_text(encoding='utf-8')))
def test_cli_brief_preserves_original_except_annotation_guidance(case):
    # Golden outputs captured from the committed CLI before extraction.
    manifest = {'targets': [{'currentPath': '/work/current.png', 'originalPath': '/work/original.png'}],
                'inputs': [{'path': '/work/screen.png'}], 'annotationPath': case['annotation']}
    prompt = wallpaper_revision_prompt(manifest, case['note'])
    if case['annotation']:
        assert ANNOTATION_GUIDANCE in prompt
        prompt = prompt.replace('\n' + ANNOTATION_GUIDANCE, '')
    assert prompt == case['prompt']


@pytest.mark.parametrize('case', json.loads(
    (Path(__file__).parent / 'fixtures/unannotated_revision_briefs.json').read_text(encoding='utf-8')))
def test_unannotated_api_and_other_cli_briefs_are_byte_for_byte_compatible(case):
    if case['mode'] == 'api':
        prompt = build_revision_prompt(current='图1', original='图2', materials=['图3'],
                                       note=case['note'], api=True)
    else:
        manifest = {'mode': case['mode'], 'singleRevision': True,
                    'targets': [{'currentPath': '/work/current.png'}],
                    'inputs': [{'path': '/work/material.png'}]}
        prompt = prompt_for(manifest, case['note'])
    assert prompt == case['prompt']


@pytest.mark.parametrize('mode', ['api', 'wallpaper', 'product', 'text'])
@pytest.mark.parametrize('note', ['', '编号1：恢复边缘。\n编号2：修正遮挡。', '修正截图中的边缘'])
def test_annotation_guidance_covers_all_single_revision_modes(mode, note):
    if mode == 'api':
        prompt = build_revision_prompt(current='图1', original='图2', materials=['图3'],
                                       annotation='图4', note=note, api=True)
    else:
        manifest = {'mode': mode, 'singleRevision': True,
                    'targets': [{'currentPath': '/work/current.png', 'originalPath': '/work/original.png'}],
                    'inputs': [{'path': '/work/material.png'}], 'annotationPath': '/work/annotation.png'}
        prompt = prompt_for(manifest, note)
    assert ANNOTATION_GUIDANCE in prompt
    assert '矩形框、自由画笔圈线和编号仅用于定位问题' in prompt
    assert '不是像素蒙版' in prompt and '这些标记不得进入成品' in prompt
    assert '图中存在编号时' in prompt and '没有编号时' in prompt
    assert '也可能是用户上传的已有截图' in prompt
    if note:
        assert json.dumps(note, ensure_ascii=False) in prompt
