import json
from pathlib import Path

import pytest

from app.image_revision_prompt import build_revision_prompt
from app.execution.prompts import wallpaper_revision_prompt


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
def test_cli_brief_is_byte_for_byte_compatible(case):
    # Golden outputs captured from the committed CLI before extraction.
    manifest = {'targets': [{'currentPath': '/work/current.png', 'originalPath': '/work/original.png'}],
                'inputs': [{'path': '/work/screen.png'}], 'annotationPath': case['annotation']}
    assert wallpaper_revision_prompt(manifest, case['note']) == case['prompt']
