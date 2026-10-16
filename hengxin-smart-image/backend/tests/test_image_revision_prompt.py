import json
from pathlib import Path

import pytest

from app.image_revision_prompt import ANNOTATION_GUIDANCE, build_revision_prompt


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




@pytest.mark.parametrize('case', [case for case in json.loads(
    (Path(__file__).parent / 'fixtures/unannotated_revision_briefs.json').read_text(encoding='utf-8')) if case['mode'] == 'api'])
def test_unannotated_api_briefs_are_byte_for_byte_compatible(case):
    prompt = build_revision_prompt(current='图1', original='图2', materials=['图3'],
                                   note=case['note'], api=True)
    assert prompt == case['prompt']


@pytest.mark.parametrize('note', ['', '编号1：恢复边缘。\n编号2：修正遮挡。', '修正截图中的边缘'])
def test_annotation_guidance_covers_api_single_revision(note):
    prompt = build_revision_prompt(current='图1', original='图2', materials=['图3'],
                                   annotation='图4', note=note, api=True)
    assert ANNOTATION_GUIDANCE in prompt
    assert '矩形框、自由画笔圈线和编号仅用于定位问题' in prompt
    assert '不是像素蒙版' in prompt and '这些标记不得进入成品' in prompt
    assert '图中存在编号时' in prompt and '没有编号时' in prompt
    assert '也可能是用户上传的已有截图' in prompt
    if note:
        assert json.dumps(note, ensure_ascii=False) in prompt
