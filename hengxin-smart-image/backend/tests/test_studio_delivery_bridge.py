"""Native presentations pass the same image gate as Markdown, without scanning."""
import base64
import json
from hashlib import sha256
from io import BytesIO
from types import SimpleNamespace

import pytest
from PIL import Image

from app.overseas.studio.delivery import collect_delivery
from app.overseas.studio.native_images import snapshot
from test_studio_native_images import SESSION, PREFIX, ENCODED, turn, write


@pytest.fixture
def case(tmp_path):
    home, work = tmp_path / 'home', tmp_path / 'work'
    work.mkdir()
    output = BytesIO()
    Image.new('RGB', (30, 40), 'blue').save(output, format='PNG')
    data = output.getvalue()
    path = home / '.codex/generated_images' / SESSION / 'exec-1.png'
    path.parent.mkdir(parents=True)
    path.write_bytes(data)
    return SimpleNamespace(home=home, work=work, baseline={}, native_cursor={},
        delivered_images=set(), data=data, file=path)


def native(case, final='已生成拼版图。', displayed=True):
    rows = json.loads(json.dumps(turn(final=final, displayed=displayed)).replace(
        ENCODED, base64.b64encode(case.data).decode()))
    return write(case.home, rows)


def collect(case, final='已生成拼版图。', **kwargs):
    return collect_delivery(case, SimpleNamespace(session_id=SESSION,
        final_text=final, turn_completed=True, error=None, **kwargs))


def test_native_without_markdown_is_delivered_and_validated(case):
    native(case)
    images, warnings = collect(case)
    assert not warnings and len(images) == 1
    assert images[0][0] == PREFIX + 'exec-1.png'
    assert images[0][1].data == case.data and images[0][1].width == 30


@pytest.mark.parametrize('final', ['草稿，尚未正式交付。', '这是临时测试图。',
    'Preview only. Not final.', '仅供预览，待确认。'])
def test_drafts_never_become_native_cards(case, final):
    native(case, final)
    assert collect(case, final) == ([], [])


def test_explicit_final_list_excludes_other_native_outputs(case):
    Image.new('RGB', (20, 20), 'red').save(case.work / 'final.png')
    final = '最终成品：![图](/work/final.png)'
    native(case, final)
    images, warnings = collect(case, final)
    assert not warnings and [path for path, _ in images] == ['/work/final.png']


def test_same_conversation_missed_image_can_be_explicitly_delivered(case):
    native(case)
    case.native_cursor = snapshot(case.home, SESSION)
    case.baseline = {'exec-1.png': sha256(case.data).hexdigest()}
    final = f'图片在这里：![图]({PREFIX}exec-1.png)'
    rows = turn('turn-2', final=final)[-2:]
    write(case.home, [{'type': 'event_msg', 'payload': {'type': 'task_started',
        'turn_id': 'turn-2'}}, *rows], append=True)
    images, warnings = collect(case, final)
    assert not warnings and len(images) == 1
    case.delivered_images = {(PREFIX + 'exec-1.png', sha256(case.data).hexdigest())}
    assert collect(case, final) == ([], [])


def test_prior_work_files_still_rejected(case):
    (case.work / 'old.png').write_bytes(case.data)
    case.work_baseline = {'old.png': sha256(case.data).hexdigest()}
    final = '![图](/work/old.png)'
    native(case, final)
    images, warnings = collect(case, final)
    assert not images and warnings


@pytest.mark.parametrize('damage', ['missing', 'changed', 'bad_evidence'])
def test_native_failure_is_visible_without_losing_text(case, damage):
    log = native(case)
    if damage == 'missing':
        case.file.unlink()
    elif damage == 'changed':
        Image.new('RGB', (30, 40), 'red').save(case.file)
    else:
        log.write_bytes(log.read_bytes()[:-10])
    images, warnings = collect(case)
    assert not images and warnings


def test_claimed_generation_without_presentation_is_not_silent(case):
    native(case, displayed=False)
    images, warnings = collect(case)
    assert not images and '未收到可验证' in warnings[0]


def test_unproven_old_native_file_is_not_accepted(case):
    final = f'![图]({PREFIX}exec-1.png)'
    native(case, final, displayed=False)
    case.baseline = {'exec-1.png': sha256(case.data).hexdigest()}
    images, warnings = collect(case, final)
    assert not images and warnings


def test_two_distinct_native_images_partial_storage_then_explicit_retry(case, monkeypatch):
    from app.overseas.studio import execution
    output = BytesIO()
    Image.new('RGB', (40, 50), 'green').save(output, format='PNG')
    second = output.getvalue()
    (case.file.parent / 'exec-2.png').write_bytes(second)
    final = '已生成两张图片。'
    rows = json.loads(json.dumps(turn(final=final)).replace(
        ENCODED, base64.b64encode(case.data).decode()))
    extra = json.loads(json.dumps(rows[1]))
    extra['payload']['item'].update(id='exec-2', savedPath=PREFIX + 'exec-2.png',
        result=base64.b64encode(second).decode())
    rows[2]['payload']['output'].append(dict(type='input_image',
        image_url='data:image/png;base64,' + base64.b64encode(second).decode()))
    rows.insert(2, extra)
    write(case.home, rows)
    images, warnings = collect(case, final)
    assert not warnings and [image.data for _, image in images] == [case.data, second]

    class Store:
        calls = 0
        def put(self, row, data):
            self.calls += 1
            if self.calls == 2:
                raise OSError('storage unavailable')
    store = Store()
    monkeypatch.setattr(execution, 'get_store', lambda: store)
    job = SimpleNamespace(task_id='task')
    summary = SimpleNamespace(final_text=final, session_id=SESSION, turn_completed=True, error=None)
    result = execution.HANDLER.validate(job, case, summary)
    assert len(result['pictures']) == 1 and '保存失败' in result['deliveryError']
    assert result['reply'] == final
    case.delivered_images = {(PREFIX + 'exec-1.png', sha256(case.data).hexdigest())}
    case.baseline = {'exec-1.png': sha256(case.data).hexdigest(), 'exec-2.png': sha256(second).hexdigest()}
    case.native_cursor = snapshot(case.home, SESSION)
    final = f'正式交付：![第一张]({PREFIX}exec-1.png)\n![第二张]({PREFIX}exec-2.png)'
    write(case.home, [dict(type='event_msg', payload=dict(type='task_started', turn_id='turn-2')),
        *turn('turn-2', final=final)[-2:]], append=True)
    summary.final_text = final
    retry = execution.HANDLER.validate(job, case, summary)
    assert len(retry['pictures']) == 1 and not retry['deliveryError']
    assert retry['pictures'][0]['checksum'] == sha256(second).hexdigest()
    assert store.calls == 3
