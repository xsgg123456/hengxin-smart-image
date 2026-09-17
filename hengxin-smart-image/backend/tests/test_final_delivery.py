import json
import os
from pathlib import Path

import pytest
from PIL import Image

from app.execution.final_delivery import collect_final_outputs
from app.execution.output_collector import OutputCollectionError


@pytest.fixture
def delivery(tmp_path):
    work, home = tmp_path / 'work', tmp_path / 'home'
    work.mkdir()
    home.mkdir()
    events = tmp_path / 'events.jsonl'

    def image(name='final.png', color='red', native=False):
        root = home / 'generated_images' / 'session-1' if native else work
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new('RGB', (16, 16), color).save(path)
        return path

    def run(reply, count=1, known=None, before=None, after=None):
        rows = [{'type': 'thread.started', 'thread_id': 'session-1'},
                {'type': 'turn.started'}]
        rows.extend(before or [])
        rows.append(message(reply))
        rows.extend(after or [])
        rows.append({'type': 'turn.completed', 'usage': {'input_tokens': 1}})
        events.write_text('\n'.join(json.dumps(row) for row in rows), encoding='utf-8')
        return collect_final_outputs(work, home, events, 'session-1', known or {}, count)

    return image, run, work, home, events


def message(text):
    return {'type': 'item.completed',
            'item': {'id': 'item_30', 'type': 'agent_message', 'text': text}}


def test_four_composited_images_ignore_extra_candidates(delivery):
    image, run, *_ = delivery
    for index, color in enumerate(('red', 'green', 'blue', 'yellow'), 1):
        image(f'final_{index}.png', color)
    image('unused_candidate.png', native=True)
    reply = '\n'.join(f'![主图{i}](/work/final_{i}.png)' for i in (4, 2, 3, 1))
    assert [item.name for item in run(reply, 4)] == [f'final_{i}.png' for i in range(1, 5)]


def test_only_final_message_and_not_tool_outputs(delivery):
    image, run, *_ = delivery
    image('chosen.png')
    before = [message('![旧图](/work/missing.png)'),
              {'type': 'item.completed', 'item': {'type': 'command_execution',
                                                 'aggregated_output': '![图](/work/tool.png)'}}]
    assert run('[下载](/work/chosen.png)', before=before)[0].name == 'chosen.png'


@pytest.mark.parametrize('after', [
    [{'type': 'item.completed', 'item': {'type': 'command_execution'}}],
    [{'type': 'item.started', 'item': {'type': 'mcp_tool_call'}}],
    [{'type': 'turn.started'}],
])
def test_progress_before_later_actions_is_not_final(delivery, after):
    image, run, *_ = delivery
    image()
    with pytest.raises(OutputCollectionError, match='final_reply_missing'):
        run('![图](/work/final.png)', after=after)


@pytest.mark.parametrize('target', [
    '/work/最终 成品 (1).png', '</work/最终 成品 (1).png>',
    '/work/%E6%9C%80%E7%BB%88%20%E6%88%90%E5%93%81%20%281%29.png',
    '最终 成品 (1).png', '/work/最终 成品 \\(1\\).png',
    '</work/最终 成品 (1).png> "下载原图"',
])
def test_path_syntax(delivery, target):
    image, run, *_ = delivery
    image('最终 成品 (1).png')
    assert run(f'[成品]({target})')[0].width == 16


def test_native_new_image_does_not_require_provenance(delivery):
    image, run, *_ = delivery
    image('native.png', native=True)
    assert run('![图](/home/runner/.codex/generated_images/session-1/native.png)')


def test_single_revision_preserves_original_task_number(delivery):
    image, run, *_ = delivery
    image()
    assert run('![主图4](/work/final.png)')[0].name == 'final.png'


def test_native_history_rejected_even_when_changed(delivery):
    image, run, *_ = delivery
    image('native.png', native=True)
    with pytest.raises(OutputCollectionError, match='historical_output_forbidden'):
        run('![图](/home/runner/.codex/generated_images/session-1/native.png)',
            known={'native.png': 'old-checksum'})


@pytest.mark.parametrize('reply,count', [('', 1), ('没有成品', 1),
    ('![图](/work/final.png)', 4),
    ('![图](/work/final.png)\n![图](/work/other.png)', 1)])
def test_incomplete_or_excess_delivery_fails(delivery, reply, count):
    _, run, *_ = delivery
    with pytest.raises(OutputCollectionError, match='final_reply_missing|final_output_count_mismatch'):
        run(reply, count)


def test_example_code_and_nonimage_links_are_not_delivery(delivery):
    image, run, *_ = delivery
    image()
    reply = ('```markdown\n![示例](/work/example.png)\n```\n'
             '`[示例](/work/inline.png)`\n    ![缩进代码](/work/code.png)\n'
             '[说明](/work/readme.md)\n![成品](/work/final.png)')
    assert len(run(reply)) == 1


@pytest.mark.parametrize('target', [
    'https://example.com/image.png', 'file:///work/final.png', '/etc/final.png',
    '/work/../other/final.png', '../final.png', '/work/%2e%2e/other.png',
    '//work/final.png', '/work/final.png?download=1', '/work/inputs/final.png',
    '/work/targets/final.png', '/work/current/final.png', '/work/skills/final.png',
    '/work/.agents/final.png', '/work/.codex/final.png',
    '/home/runner/.codex/generated_images/other-session/final.png',
    '/work/one%00.png', '/work/one%5c.png',
])
def test_unsafe_paths(delivery, target):
    _, run, *_ = delivery
    with pytest.raises(OutputCollectionError):
        run(f'![图]({target})')


def test_missing_and_corrupt_files(delivery):
    _, run, work, *_ = delivery
    with pytest.raises(OutputCollectionError, match='invalid_output_file'):
        run('![图](/work/missing.png)')
    (work / 'broken.png').write_bytes(b'not a picture')
    with pytest.raises(OutputCollectionError, match='invalid_output_image'):
        run('![图](/work/broken.png)')
    (work / 'directory.png').mkdir()
    with pytest.raises(OutputCollectionError, match='invalid_output_file'):
        run('![图](/work/directory.png)')


def test_duplicate_path_alias_is_rejected(delivery):
    image, run, *_ = delivery
    image()
    with pytest.raises(OutputCollectionError, match='invalid_final_reply'):
        run('![一](/work/final.png)\n[二](final.png)', 2)


@pytest.mark.parametrize('label', ['主图 ({i})', '主图（{i}）', '第{i}张', '图片{i}', '图{i}'])
def test_number_variants_reorder_instead_of_silently_assigning_wrong_slots(delivery, label):
    image, run, *_ = delivery
    for i in range(1, 5):
        image(f'{i}.png')
    reply = '\n'.join(f'![{label.format(i=i)}](/work/{i}.png)' for i in (4, 2, 3, 1))
    assert [item.name for item in run(reply, 4)] == [f'{i}.png' for i in range(1, 5)]


def test_chinese_numbering(delivery):
    image, run, *_ = delivery
    image('a.png')
    image('b.png')
    assert [item.name for item in run('[第二张](/work/b.png) [第一张](/work/a.png)', 2)] == ['a.png', 'b.png']


def test_preview_and_download_references_merge_by_path_without_losing_number(delivery):
    image, run, *_ = delivery
    for i in range(1, 5):
        image(f'final ({i}).png')
    reply = '\n'.join(f'![主图 ({i})](/work/final ({i}).png) [下载](<final%20({i}).png>)'
                      for i in (4, 2, 3, 1))
    assert [item.name for item in run(reply, 4)] == [f'final ({i}).png' for i in range(1, 5)]


def test_same_file_cannot_fill_two_numbered_slots(delivery):
    image, run, *_ = delivery
    image()
    with pytest.raises(OutputCollectionError, match='invalid_final_reply'):
        run('![主图1](/work/final.png) [主图2](final.png)', 2)


@pytest.mark.parametrize('layout', [
    '### 主图 {i}（已修复）\n![成品](/work/{i}.png)',
    '### 主图 {i}（已修复）\n尺寸检查通过。\n![成品](/work/{i}.png)',
    '![{i}](/work/{i}.png)',
    '{i}、[下载成品](/work/{i}.png)',
    '{i}. [下载成品](/work/{i}.png)',
    '**第{i}张（已修复）**\n[下载成品](/work/{i}.png)',
])
def test_numbered_headings_labels_and_lists_with_explanatory_text(delivery, layout):
    image, run, *_ = delivery
    for i in range(1, 5):
        image(f'{i}.png')
    assert [item.name for item in run('\n\n'.join(layout.format(i=i) for i in (4, 2, 3, 1)), 4)] == [
        f'{i}.png' for i in range(1, 5)]


def test_disagreeing_heading_and_numeric_label_is_rejected(delivery):
    _, run, *_ = delivery
    with pytest.raises(OutputCollectionError, match='invalid_final_reply'):
        run('### 主图2（已修复）\n![1](/work/a.png)\n![2](/work/b.png)', 2)


@pytest.mark.parametrize('reply', [
    '![主图1](/work/a.png)\n![主图1](/work/b.png)',
    '![主图1](/work/a.png)\n![无编号](/work/b.png)',
    '![主图1](/work/a.png)\n![主图3](/work/b.png)',
    '主图2: ![主图1](/work/a.png)\n![主图2](/work/b.png)',
])
def test_conflicting_numbering(delivery, reply):
    _, run, *_ = delivery
    with pytest.raises(OutputCollectionError, match='invalid_final_reply'):
        run(reply, 2)


@pytest.mark.parametrize('reply', [
    '![主图2](/work/b.png) ![主图1](/work/a.png)',
    '### 主图2\n![图](/work/b.png)\n### 主图1\n![图](/work/a.png)',
    '[下载第一张](/work/a.png)\n[下载第二张](/work/b.png)',
])
def test_number_or_display_order(delivery, reply):
    image, run, *_ = delivery
    image('a.png')
    image('b.png')
    assert [item.name for item in run(reply, 2)] == ['a.png', 'b.png']


def test_link_files_are_rejected(delivery):
    image, run, work, *_ = delivery
    original = image()
    os.link(original, work / 'hard.png')
    with pytest.raises(OutputCollectionError, match='output_hardlink_forbidden'):
        run('![图](/work/hard.png)')
    try:
        (work / 'soft.png').symlink_to(original)
    except OSError:
        pytest.skip('symlinks unavailable on this host')
    with pytest.raises(OutputCollectionError, match='output_link_forbidden'):
        run('![图](/work/soft.png)')


def test_event_corruption_and_session_mismatch(delivery):
    _, _, work, home, events = delivery
    events.write_text('{invalid json', encoding='utf-8')
    with pytest.raises(OutputCollectionError, match='invalid_event_stream'):
        collect_final_outputs(work, home, events, 'session-1', {}, 1)
    events.write_text(json.dumps({'type': 'thread.started', 'thread_id': 'other'}), encoding='utf-8')
    with pytest.raises(OutputCollectionError, match='session_mismatch'):
        collect_final_outputs(work, home, events, 'session-1', {}, 1)
