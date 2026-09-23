import json

import pytest

from app.execution.prompts import prompt_for


@pytest.mark.parametrize('name', ['jd-detail-screen-swap', 'jd-detail-screen-swap-790x1500',
    'jd-main-image-wallpaper-camera-swap', 'jd-main-image-wallpaper-camera-swap-it-optimized'])
@pytest.mark.parametrize('annotation,note', [(False, '镜头向左移动'), (True, ''),
    (True, '只修改圈内位置\n不要改变其他内容')])
def test_single_revision_uses_only_finished_image_reference_and_feedback(name, annotation, note):
    manifest = {'mode': 'wallpaper', 'singleRevision': True,
        'skillPath': f'/work/skills/{name}/SKILL.md',
        'targets': [{'slot': 0, 'taskSlot': 2, 'path': '/work/targets/00.jpg',
                     'currentPath': '/work/current/00.png', 'currentVersion': 1}],
        'inputs': [{'path': '/work/inputs/00.jpg'}]}
    if annotation:
        manifest['annotationPath'] = '/work/annotation/reference.png'
    expected = ['请修改这张成品图片：', '- /work/current/00.png', '',
                '手机屏幕参考素材：', '- /work/inputs/00.jpg']
    if annotation:
        expected += ['', '问题位置参考图：', '- /work/annotation/reference.png',
                     '该图仅用于定位问题，标注内容不要出现在成品中。']
    if note:
        expected += ['', '修改意见：', json.dumps(note, ensure_ascii=False)]
    expected += ['', '请在上述成品图片上完成修改，其他内容保持不变，只交付修改后的这 1 张图片。']
    assert prompt_for(manifest, note, 'original-session') == '\n'.join(expected)
    del manifest['skillPath']
    del manifest['targets'][0]['path']
    assert prompt_for(manifest, note, 'original-session') == '\n'.join(expected)


@pytest.mark.parametrize('mode,role', [('product', '商品参考素材'), ('text', None)])
def test_single_revision_other_modes_keep_material_meaning(mode, role):
    manifest = {'mode': mode, 'singleRevision': True,
        'targets': [{'currentPath': '/work/current/00.png'}],
        'inputs': [{'path': '/work/inputs/00.jpg'}]}
    prompt = prompt_for(manifest, '修改', 'original-session')
    assert '手机屏幕' not in prompt
    assert ('/work/inputs/00.jpg' in prompt) == bool(role)
    if role:
        assert role in prompt


def test_no_result_single_retry_keeps_generation_instructions():
    manifest = {'mode': 'wallpaper', 'singleRevision': True,
        'skillPath': '/work/skills/jd-detail-screen-swap/SKILL.md',
        'targets': [{'slot': 0, 'path': '/work/targets/00.jpg'}],
        'inputs': [{'path': '/work/inputs/00.jpg'}]}
    prompt = prompt_for(manifest, '重试', 'original-session')
    assert '使用 $jd-detail-screen-swap' in prompt and '/work/targets/00.jpg' in prompt
    assert '请修改这张成品图片' not in prompt
