import json
from pathlib import Path

import pytest

from app.execution.prompts import prompt_for
from app.execution.workspace import Workspace


def materials(mode='wallpaper', count=4):
    return {'mode': mode, 'skillPath': '/work/skills/jd-main-image-wallpaper-camera-swap-it-optimized/SKILL.md',
            'inputs': [{'slot': 0, 'path': '/work/inputs/00.png'}],
            'targets': [{'slot': i, 'taskSlot': i, 'path': f'/work/targets/{i:02d}.jpg'} for i in range(count)]}


def test_wallpaper_brief_matches_manual_format_with_all_actual_images():
    data = materials()
    prompt = prompt_for(data, '')
    assert prompt.startswith('使用 $jd-main-image-wallpaper-camera-swap-it-optimized。\n请读取服务器目录 /work/：')
    assert '第 4 张待修改底图（共 4 张）' in prompt and '手机屏幕素材' in prompt
    assert '把这张手机屏幕素材替换掉图片的壁纸与镜头，其他一律不允许有任何改变。' in prompt
    for item in data['inputs'] + data['targets']:
        assert item['path'] in prompt
    for internal in ('后台结果交付规则', 'manifest.json', 'generated_images', 'slot', '本次补充要求'):
        assert internal not in prompt


@pytest.mark.parametrize('mode', ['product', 'text'])
def test_other_modes_do_not_receive_phone_instructions(mode):
    prompt = prompt_for(materials(mode), '自定义修改要求')
    assert '手机屏幕' not in prompt and '壁纸与镜头' not in prompt
    assert '自定义修改要求' in prompt


def test_rework_keeps_current_image_original_target_and_local_slot_zero():
    data = materials(count=1)
    data['targets'][0].update(taskSlot=3, currentPath='/work/current/00.webp', currentVersion=2)
    prompt = prompt_for(data, '镜头向左移动一点', 'existing-session')
    assert '本次为返工' in prompt and '本轮修改意见' in prompt
    assert '/work/current/00.webp' in prompt and '/work/targets/00.jpg' in prompt
    assert '第 1 张底图的当前版本' in prompt and 'taskSlot' not in prompt
    assert '"镜头向左移动一点"' in prompt


def test_multiple_inputs_and_rework_without_successful_current_result():
    data = materials(count=2)
    data['inputs'].append({'slot': 1, 'path': '/work/inputs/01.webp'})
    prompt = prompt_for(data, '重新处理失败图', 'existing-session')
    assert '共 2 张' in prompt and '把这些手机屏幕素材' in prompt
    assert '/work/inputs/01.webp' in prompt and '没有当前结果的图片使用原底图' in prompt


@pytest.mark.parametrize('name', ['../escape', '/root', 'a/b', 'a\\b', '', 'x\n'])
def test_mount_identifier_cannot_escape_skills(name):
    with pytest.raises(ValueError):
        _ = Workspace(Path('home'), Path('work'), Path('control'), skill_name=name).skill_path
