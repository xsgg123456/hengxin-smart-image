"""Diagnostics must not turn untrusted evidence into public text or platform claims."""

import json
import os

import pytest

from app.execution.diagnostics import cli_failure_code, failure_for, manifest_failure

CASE = ('原生图片工具已独立生成并从原模板重试，但输出均为1254×1254，'
        '与模板800×800不符；按编辑规则禁止缩放修正，未通过验收。')
SECRET = 'sk-secret-123 Bearer abc /home/private/input.png C:\\private\\key rm -rf / https://secret.example'
SAFE_OPEN = os.open in os.supports_dir_fd and hasattr(os, 'O_NOFOLLOW')
requires_safe_open = pytest.mark.skipif(not SAFE_OPEN, reason='safe descriptor reads require POSIX')


def write_manifest(tmp_path, entries):
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps({'outputs': entries}, ensure_ascii=False), encoding='utf-8')
    return path


@pytest.mark.parametrize('code', [
    'output_path_escape', 'output_link_forbidden', 'output_hardlink_forbidden', 'manifest_link_forbidden',
    'invalid_output_manifest', 'output_manifest_required', 'historical_manifest_forbidden',
    'output_count_or_manifest_mismatch', 'invalid_output_count', 'invalid_output_directory',
    'invalid_output_file', 'historical_output_changed', 'invalid_output_image',
    'invalid_provenance_directory', 'provenance_hardlink_forbidden', 'invalid_provenance_file',
    'historical_provenance_changed', 'incomplete_provenance_baseline', 'invalid_provenance_record',
    'provenance_session_or_turn_mismatch', 'invalid_generation_provenance', 'provenance_saved_path_mismatch',
    'invalid_generation_payload', 'invalid_provenance_baseline', 'conflicting_generation_provenance',
    'invalid_provenance_outputs', 'image_generation_provenance_missing', 'invalid_event_stream',
    'unreadable_event_stream', 'invalid_session_id', 'session_mismatch', 'invalid_turn_id', 'invalid_usage',
    'cli_error', 'turn_failed', 'timeout', 'cancelled', 'output_limit', 'startup_failed', 'storage_failed',
    'publication_lost', 'unexpected_error', 'all_outputs_failed', 'execution_uncertain', 'legacy_failure',
    'authentication_failed', 'network_failed', 'rate_limited',
])
def test_internal_codes_have_fixed_messages(code):
    report = failure_for(code, 'generating')
    assert report['code'] != 'UNKNOWN'
    assert report['stage'] == 'generating'
    assert report['message'] and report['action'] and report['slotErrors'] == []
    assert set(report) == {'code', 'message', 'action', 'stage', 'slotErrors'}


@pytest.mark.parametrize('value', [SECRET, 'timeout ' + SECRET, '', None, [], {}, 1])
def test_unknown_code_and_stage_never_echo(value):
    report = failure_for(value, value)
    assert report == failure_for('unknown', 'failed')
    assert report['code'] == 'UNKNOWN'
    assert SECRET not in json.dumps(report)


def test_reports_do_not_share_mutable_lists():
    failure_for('timeout', 'failed')['slotErrors'].append({'slot': 10})
    assert failure_for('timeout', 'failed')['slotErrors'] == []


@requires_safe_open
@pytest.mark.parametrize('error', [CASE, '原生输出1254×1254，与模板800×800不符，禁止缩放修正'])
def test_screenshot_dimensions_per_original_slot(tmp_path, error):
    path = write_manifest(tmp_path, [{'slot': 1, 'error': error}, {'slot': 0, 'error': error}])
    report = manifest_failure(path, 2)
    assert report['code'] == 'ALL_OUTPUTS_FAILED'
    assert [entry['slot'] for entry in report['slotErrors']] == [0, 1]
    for entry in report['slotErrors']:
        assert entry['code'] == 'SKILL_DIMENSION_MISMATCH'
        assert '输出 1254×1254，目标 800×800' in entry['message']
        assert 'Skill' in entry['message'] and '非平台验证' in entry['message']
        assert '原生图片工具' not in entry['message']


@requires_safe_open
@pytest.mark.parametrize('error,code', [
    (CASE, 'SKILL_DIMENSION_MISMATCH'), ('网络连接失败', 'SKILL_NETWORK_FAILED'),
    ('authentication failed', 'SKILL_AUTH_FAILED'), ('内容被拒绝', 'SKILL_CONTENT_REJECTED'),
    ('arbitrary model output', 'SKILL_REPORTED_FAILURE'),
])
def test_sensitive_prose_never_returned(tmp_path, error, code):
    path = write_manifest(tmp_path, [{'slot': 0, 'error': error + ' ' + SECRET}])
    report = manifest_failure(path, 1)
    assert report['slotErrors'][0]['code'] == code
    rendered = json.dumps(report, ensure_ascii=False)
    for token in ('sk-secret', 'Bearer', 'private', 'rm -rf', 'https://', 'arbitrary model output'):
        assert token not in rendered
    if code == 'SKILL_REPORTED_FAILURE':
        assert report['slotErrors'][0]['message'] == 'Skill报告该图处理失败，需核对输入与要求'


@requires_safe_open
@pytest.mark.parametrize('error', [
    '尺寸不符：1254×1254、800×800', '尺寸不符，模板800×800，另一组1254×1254',
    '尺寸不符，输出为99999×99999，模板800×800',
    '尺寸不符，输出为1254×1254，输出为800×800，模板800×800',
    '尺寸不符，输出为800×800，模板800×800',
    '尺寸不符，输出为123456×1254，模板800×800',
])
def test_no_guessed_or_unbounded_dimensions(tmp_path, error):
    path = write_manifest(tmp_path, [{'slot': 0, 'error': error}])
    message = manifest_failure(path, 1)['slotErrors'][0]['message']
    assert 'SKILL' not in message and '尺寸' in message
    assert not any(char.isdigit() for char in message)


@requires_safe_open
@pytest.mark.parametrize('error', [
    '1254×1254，与800×800不符', '输出1254×1254，与800×800不符',
    '1254×1254，与模板800×800不符', '输出1254×1254，模板800×800',
])
def test_unlabelled_numbers_or_missing_mismatch_are_not_inferred(tmp_path, error):
    path = write_manifest(tmp_path, [{'slot': 0, 'error': error}])
    slot_error = manifest_failure(path, 1)['slotErrors'][0]
    assert slot_error['code'] == 'SKILL_REPORTED_FAILURE'
    assert not any(char.isdigit() for char in slot_error['message'])


@requires_safe_open
def test_partial_success_and_target_mapping(tmp_path):
    path = write_manifest(tmp_path, [{'slot': 1, 'error': CASE}, {'slot': 0, 'file': 'safe/image.png'}])
    report = manifest_failure(path, 2)
    assert report['code'] == 'SKILL_OUTPUT_FAILED'
    assert [entry['slot'] for entry in report['slotErrors']] == [1]
    assert manifest_failure(path, 2, target=8) is None
    path = write_manifest(tmp_path, [{'slot': 0, 'error': CASE}])
    assert manifest_failure(path, 1, target=8)['slotErrors'][0]['slot'] == 8
    assert manifest_failure(path, 1, target=0)['slotErrors'][0]['slot'] == 0


@requires_safe_open
@pytest.mark.parametrize('entries', [
    None, {}, [], [None], ['oops'], [{'slot': True, 'error': 'failed'}],
    [{'slot': 0.0, 'error': 'failed'}], [{'slot': '0', 'error': 'failed'}],
    [{'slot': -1, 'error': 'failed'}], [{'slot': 1, 'error': 'failed'}],
    [{'slot': 0}], [{'slot': 0, 'error': ''}], [{'slot': 0, 'error': ' \t'}],
    [{'slot': 0, 'error': 1}], [{'slot': 0, 'error': 'x' * 1001}],
    [{'slot': 0, 'error': 'failed', 'file': 'image.png'}],
    [{'slot': 0, 'error': 'failed', 'secret': SECRET}],
])
def test_invalid_entries(tmp_path, entries):
    assert manifest_failure(write_manifest(tmp_path, entries), 1) is None


@requires_safe_open
@pytest.mark.parametrize('name', ['', ' ', '/etc/passwd', '../foo', 'foo/../bar', './foo', 'foo//bar',
                                 'C:/secret', 'foo\\bar', 'foo\x00bar', 'foo\nbar', {}, None, 1])
def test_invalid_file_even_with_other_valid_error(tmp_path, name):
    path = write_manifest(tmp_path, [{'slot': 0, 'file': name}, {'slot': 1, 'error': CASE}])
    assert manifest_failure(path, 2) is None


@requires_safe_open
@pytest.mark.parametrize('raw', [
    '[]', 'null', '42', '{', '{"outputs":[],"outputs":[]}',
    '{"outputs":[{"slot":0,"error":"bad","error":"worse"}]}',
    '{"outputs":[{"slot":0,"error":"bad"}],"other":1}',
    '[' * 2000 + ']' * 2000,
])
def test_invalid_json_shape(tmp_path, raw):
    path = tmp_path / 'manifest.json'
    path.write_text(raw)
    assert manifest_failure(path, 1) is None


@requires_safe_open
def test_counts_duplicates_success_and_error_length_boundary(tmp_path):
    for entries, count in [([{'slot': 0, 'error': CASE}] * 2, 2),
                           ([{'slot': i, 'file': 'same.png'} for i in range(2)], 2),
                           ([{'slot': 0, 'error': CASE}], 2),
                           ([{'slot': 0, 'file': 'image.png'}], 1)]:
        assert manifest_failure(write_manifest(tmp_path, entries), count) is None
    path = write_manifest(tmp_path, [{'slot': 0, 'error': 'x' * 1000}])
    assert manifest_failure(path, 1) is not None
    for count, target in [(True, None), (0, None), (-1, None), (1.0, None), (1, True), (1, -1), (1, '2')]:
        assert manifest_failure(path, count, target) is None


@requires_safe_open
def test_missing_oversized_invalid_encoding_and_exact_limit(tmp_path):
    path = tmp_path / 'manifest.json'
    assert manifest_failure(path, 1) is None
    path.write_bytes(b'\xff')
    assert manifest_failure(path, 1) is None
    raw = b'{"outputs":[{"slot":0,"error":"failed"}]}'
    path.write_bytes(raw + b' ' * (65536 - len(raw)))
    assert manifest_failure(path, 1) is not None
    path.write_bytes(path.read_bytes() + b' ')
    assert manifest_failure(path, 1) is None
    assert manifest_failure(tmp_path, 1) is None


@requires_safe_open
def test_links_and_fifo_rejected_by_both_readers(tmp_path):
    real = tmp_path / 'real'
    real.mkdir()
    path = write_manifest(real, [{'slot': 0, 'error': 'Unauthorized'}])
    link = tmp_path / 'linked.json'
    link.symlink_to(path)
    parent = tmp_path / 'parent'
    parent.symlink_to(real, target_is_directory=True)
    hard = tmp_path / 'hard.json'
    os.link(path, hard)
    fifo = tmp_path / 'pipe'
    os.mkfifo(fifo)
    for unsafe in (link, parent / 'manifest.json', hard, path, fifo):
        assert manifest_failure(unsafe, 1) is None
        assert cli_failure_code(unsafe, 'turn_failed') == 'turn_failed'


@requires_safe_open
@pytest.mark.parametrize('text,code', [
    ('HTTP 401 ' + SECRET, 'authentication_failed'), ('Unauthorized', 'authentication_failed'),
    ('Authentication Failed', 'authentication_failed'), ('connection reset', 'network_failed'),
    ('connection refused', 'network_failed'), ('failed to connect', 'network_failed'),
    ('DNS lookup failure', 'network_failed'), ('HTTP 429', 'rate_limited'),
    ('rate limit exceeded', 'rate_limited'), ('rate-limited', 'rate_limited'),
    ('14012 14290 ' + SECRET, 'turn_failed'), ('unrecognized ' + SECRET, 'turn_failed'),
])
def test_cli_classification_only_returns_codes(tmp_path, text, code):
    path = tmp_path / 'stderr.log'
    path.write_text(text, encoding='utf-8')
    assert cli_failure_code(path, 'turn_failed') == code


@requires_safe_open
def test_cli_only_inspects_bounded_tail(tmp_path):
    path = tmp_path / 'stderr.log'
    path.write_bytes(b'Unauthorized ' + b' ' * 32768)
    assert cli_failure_code(path) == 'cli_error'
    path.write_bytes(b' ' * 65536 + b'connection reset')
    assert cli_failure_code(path) == 'network_failed'
    assert cli_failure_code(tmp_path / 'missing', SECRET) == 'cli_error'
    assert cli_failure_code(tmp_path) == 'cli_error'


def test_no_safe_open_support_fails_closed(tmp_path, monkeypatch):
    path = write_manifest(tmp_path, [{'slot': 0, 'error': 'Unauthorized'}])
    monkeypatch.setattr(os, 'supports_dir_fd', set())
    assert manifest_failure(path, 1) is None
    assert cli_failure_code(path) == 'cli_error'


@pytest.mark.parametrize('stage', ['queued', 'preparing', 'starting', 'generating', 'validating',
                                  'storing', 'publishing', 'completed', 'failed', 'cancelled', 'uncertain'])
def test_defined_stages_are_preserved(stage):
    assert failure_for('storage_failed', stage)['stage'] == stage


@requires_safe_open
def test_explicit_labels_not_numeric_order(tmp_path):
    error = '模板800×800，与实际尺寸为1254×1254不符'
    path = write_manifest(tmp_path, [{'slot': 0, 'error': error}])
    assert '输出 1254×1254，目标 800×800' in manifest_failure(path, 1)['slotErrors'][0]['message']


@requires_safe_open
def test_read_errors_do_not_escape(tmp_path, monkeypatch):
    path = write_manifest(tmp_path, [{'slot': 0, 'error': CASE}])

    def denied(*args, **kwargs):
        raise PermissionError('private sensitive error')

    monkeypatch.setattr(os, 'fstat', denied)
    assert manifest_failure(path, 1) is None
    assert cli_failure_code(path, 'turn_failed') == 'turn_failed'


@requires_safe_open
def test_concurrent_link_swap_rejected(tmp_path, monkeypatch):
    path = write_manifest(tmp_path, [{'slot': 0, 'error': CASE}])
    evil = tmp_path / 'evil.json'
    evil.write_text('{"outputs":[{"slot":0,"error":"Unauthorized"}]}')
    original_open = os.open

    def swap_before_open(name, flags, **kwargs):
        if name == path.name and not path.is_symlink():
            path.unlink()
            path.symlink_to(evil)
        return original_open(name, flags, **kwargs)

    monkeypatch.setattr(os, 'open', swap_before_open)
    monkeypatch.setattr(os, 'supports_dir_fd', {swap_before_open})
    assert manifest_failure(path, 1) is None
    assert cli_failure_code(path) == 'cli_error'
