import json

import pytest

from app.execution.prompts import prompt_for


@pytest.mark.parametrize('name', ['jd-detail-screen-swap', 'jd-detail-screen-swap-790x1500',
    'jd-main-image-wallpaper-camera-swap', 'jd-main-image-wallpaper-camera-swap-it-optimized'])
@pytest.mark.parametrize('annotation,note', [(False, '镜头向左移动'), (True, ''),
    (True, '只修改圈内位置\n不要改变其他内容')])
def test_wallpaper_revision_includes_original_with_distinct_roles(name, annotation, note):
    manifest = {'mode': 'wallpaper', 'singleRevision': True,
        'skillPath': f'/work/skills/{name}/SKILL.md',
        'targets': [{'slot': 0, 'taskSlot': 2, 'path': '/work/targets/00.jpg',
                     'originalPath': '/work/original/00.jpg',
                     'currentPath': '/work/current/00.png', 'currentVersion': 1}],
        'inputs': [{'path': '/work/inputs/00.jpg'}]}
    if annotation:
        manifest['annotationPath'] = '/work/annotation/reference.png'
    prompt = prompt_for(manifest, note, 'original-session')
    sections = ['当前成品：', '/work/current/00.png', '对应原始底图：',
                '/work/original/00.jpg', '手机屏幕素材：', '/work/inputs/00.jpg']
    assert [prompt.index(part) for part in sections] == sorted(prompt.index(part) for part in sections)
    assert ('问题位置参考图：' in prompt) == annotation
    assert ('/work/annotation/reference.png' in prompt) == annotation
    assert ('本次修改意见：' in prompt) == bool(note)
    if note:
        assert json.dumps(note, ensure_ascii=False) in prompt
    assert '这是本次唯一修改对象' in prompt and '不要恢复旧壁纸' in prompt
    assert '输出前，将修复位置及周边交界' in prompt
    assert '只展示并提供修改后的这1张成品图片' in prompt
    assert '使用 $' not in prompt and '/work/targets/' not in prompt
    del manifest['skillPath']
    del manifest['targets'][0]['path']
    assert prompt_for(manifest, note, 'original-session') == prompt


def test_wallpaper_revision_requires_explicit_original():
    with pytest.raises(KeyError, match='originalPath'):
        prompt_for({'mode': 'wallpaper', 'singleRevision': True,
                    'targets': [{'currentPath': '/work/current/00.png'}], 'inputs': []}, '修改')


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
