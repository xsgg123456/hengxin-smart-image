"""Public diagnostics from fixed codes and untrusted Skill manifests, never prose passthrough."""

import json
import os
import re
import stat
from pathlib import Path

STAGES = frozenset(('queued', 'preparing', 'starting', 'generating', 'validating',
                    'storing', 'publishing', 'completed', 'failed', 'cancelled', 'uncertain'))
MAX_MANIFEST_BYTES = 64 * 1024
_RETRY = '请重试；若仍失败，请联系管理员并提供诊断编号'
_GROUPS = (
    ('SKILL_DEPLOYMENT_INVALID', '冻结 Skill 版本缺失、内容变化或隔离环境依赖不可用',
     '请联系管理员检查该版本部署；平台不会自动切换版本', 'skill_deployment_invalid'),
    ('OUTPUT_UNSAFE', '输出文件未通过安全检查', _RETRY,
     'output_path_escape output_link_forbidden output_hardlink_forbidden manifest_link_forbidden'),
    ('OUTPUT_MANIFEST_INVALID', '输出清单缺失或不符合约定', '请检查 Skill 输出清单约定后重试',
     'invalid_output_manifest output_manifest_required historical_manifest_forbidden '
     'output_count_or_manifest_mismatch invalid_output_count'),
    ('OUTPUT_INVALID', '输出文件无效或历史输出被修改', _RETRY,
     'invalid_output_directory invalid_output_file historical_output_changed'),
    ('OUTPUT_IMAGE_INVALID', '输出图片未通过平台图片校验', '请核对图片格式与文件完整性后重试',
     'invalid_output_image'),
    ('PROVENANCE_INVALID', '输出图片未通过平台来源验证', '请检查原生生图工具的执行记录后重试',
     'invalid_provenance_directory provenance_hardlink_forbidden invalid_provenance_file '
     'historical_provenance_changed incomplete_provenance_baseline invalid_provenance_record '
     'provenance_session_or_turn_mismatch invalid_generation_provenance provenance_saved_path_mismatch '
     'invalid_generation_payload invalid_provenance_baseline conflicting_generation_provenance '
     'invalid_provenance_outputs image_generation_provenance_missing'),
    ('EXECUTION_RECORD_INVALID', '执行记录未通过平台校验', _RETRY,
     'invalid_event_stream unreadable_event_stream invalid_session_id session_mismatch '
     'invalid_turn_id invalid_usage'),
    ('CLI_ERROR', '图片执行工具异常退出', _RETRY, 'cli_error'),
    ('TURN_FAILED', '本轮图片处理执行失败', _RETRY, 'turn_failed'),
    ('TIMEOUT', '图片处理超过执行时限', '请稍后重试或减少本轮处理数量', 'timeout'),
    ('CANCELLED', '本轮图片处理已取消', '需要继续时请重新发起处理', 'cancelled'),
    ('OUTPUT_LIMIT', '执行输出超过允许上限', '请检查 Skill 输出量后重试', 'output_limit'),
    ('STARTUP_FAILED', '图片执行工具启动失败', '请联系管理员检查执行环境', 'startup_failed'),
    ('STORAGE_FAILED', '图片结果存储失败', '请联系管理员检查存储服务', 'storage_failed'),
    ('PUBLICATION_LOST', '本轮结果未能完成发布', '请刷新任务状态，仍异常时联系管理员', 'publication_lost'),
    ('UNEXPECTED_ERROR', '图片处理发生未预期异常', _RETRY, 'unexpected_error'),
    ('ALL_OUTPUTS_FAILED', '本轮所有图片均处理失败', '请核对输入与要求后重试', 'all_outputs_failed'),
    ('EXECUTION_UNCERTAIN', '本轮执行结果暂无法确认', '请刷新任务状态，仍异常时联系管理员', 'execution_uncertain'),
    ('LEGACY_FAILURE', '本轮处理失败，历史记录未保留详细诊断', '请核对输入与要求后重试', 'legacy_failure'),
    ('AUTHENTICATION_FAILED', '图片执行工具认证失败', '请联系管理员检查执行工具认证配置', 'authentication_failed'),
    ('NETWORK_FAILED', '图片执行工具网络连接失败', '请稍后重试，仍失败时联系管理员检查网络', 'network_failed'),
    ('RATE_LIMITED', '图片执行工具请求受到限流', '请稍后重试', 'rate_limited'),
    ('SKILL_OUTPUT_FAILED', 'Skill 报告部分图片处理失败（非平台验证结论）',
     '请核对逐图说明、输入与要求后重试', 'skill_output_failed'),
)
_FAILURES = {key: (code, message, action) for code, message, action, keys in _GROUPS
             for key in keys.split()}


def failure_for(code: str, stage: str) -> dict:
    """Only exact internal codes are accepted; unknown stages become ``failed``."""
    result = _FAILURES.get(code) if type(code) is str else None
    public_code, message, action = result or ('UNKNOWN', '图片处理失败，原因暂未确定', _RETRY)
    return {'code': public_code, 'message': message, 'action': action,
            'stage': stage if type(stage) is str and stage in STAGES else 'failed', 'slotErrors': []}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate key')
        result[key] = value
    return result


def _safe_read(path: Path, limit: int, *, tail: bool = False,
               allow_windows_fallback: bool = False) -> bytes:
    # Walk directory descriptors so even concurrently replaced parent symlinks
    # cannot redirect the read on POSIX hosts.
    if os.open not in os.supports_dir_fd or not hasattr(os, 'O_NOFOLLOW'):
        if not allow_windows_fallback:
            raise OSError('safe open unavailable')
        # Windows has no O_NOFOLLOW/O_DIRECTORY pair. Reject links at every
        # path component and verify the file identity before and after reading;
        # this preserves diagnostics on the supported Windows dev machine while
        # keeping the fallback fail-closed for link-based path escapes.
        path = Path(path).absolute()
        if '..' in path.parts:
            raise ValueError('parent traversal')
        components = (path, *path.parents)
        if any(part.is_symlink() or bool(getattr(part, 'is_junction', lambda: False)())
               for part in components):
            raise ValueError('unsafe manifest')
        before = path.stat()
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
                or (not tail and before.st_size > limit)):
            raise ValueError('unsafe manifest')
        with path.open('rb') as stream:
            if tail:
                stream.seek(max(0, before.st_size - limit))
            raw = stream.read(limit if tail else limit + 1)
        after = path.stat()
        if (len(raw) > limit or after.st_nlink != 1
                or (before.st_size, before.st_mtime_ns, before.st_ctime_ns)
                != (after.st_size, after.st_mtime_ns, after.st_ctime_ns)):
            raise ValueError('changed manifest')
        return raw
    path = Path(path).absolute()
    if '..' in path.parts:
        raise ValueError('parent traversal')
    directory = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in path.parts[1:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory)
            directory = child
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        with os.fdopen(fd, 'rb') as stream:
            before = os.fstat(stream.fileno())
            if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
                    or (not tail and before.st_size > limit)):
                raise ValueError('unsafe manifest')
            if tail:
                stream.seek(max(0, before.st_size - limit))
            raw = stream.read(limit if tail else limit + 1)
            after = os.fstat(stream.fileno())
            if (len(raw) > limit or after.st_nlink != 1
                    or (before.st_size, before.st_mtime_ns, before.st_ctime_ns)
                    != (after.st_size, after.st_mtime_ns, after.st_ctime_ns)):
                raise ValueError('changed manifest')
            return raw
    finally:
        os.close(directory)


def cli_failure_code(stderr_path: Path, default: str = 'cli_error') -> str:
    """Classify at most the final 32 KiB, only after the caller establishes CLI failure."""
    fallback = default if type(default) is str and default in _FAILURES else 'cli_error'
    try:
        text = _safe_read(stderr_path, 32 * 1024, tail=True).decode('utf-8', errors='replace')
    except (OSError, ValueError, TypeError):
        return fallback
    for code, pattern in (
        ('authentication_failed', r'(?<![\w])401(?![\w])|\bunauthorized\b|authentication failed'),
        ('network_failed', r'connection (?:reset|refused)|failed to connect|\bdns\b'),
        ('rate_limited', r'(?<![\w])429(?![\w])|\brate[ -]limit(?:ed|ing)?\b'),
    ):
        if re.search(pattern, text, re.IGNORECASE):
            return code
    return fallback


def _valid_file(value) -> bool:
    # Syntax validation only: existence and image/provenance checks belong to the collector.
    return (type(value) is str and bool(value.strip()) and len(value) <= 1000
            and not any(ord(char) < 32 or ord(char) == 127 for char in value)
            and not any(char in value for char in '\\:')
            and all(part not in ('', '.', '..') for part in value.split('/')))


def _entries(document, count: int) -> list[dict]:
    if type(document) is not dict or set(document) != {'outputs'}:
        raise ValueError('invalid document')
    entries = document['outputs']
    if type(entries) is not list or len(entries) != count:
        raise ValueError('invalid count')
    slots, files = set(), set()
    for entry in entries:
        if type(entry) is not dict or set(entry) not in ({'slot', 'file'}, {'slot', 'error'}):
            raise ValueError('invalid entry')
        slot = entry['slot']
        if type(slot) is not int or not 0 <= slot < count or slot in slots:
            raise ValueError('invalid slot')
        slots.add(slot)
        if 'error' in entry:
            error = entry['error']
            if type(error) is not str or not error.strip() or len(error) > 1000:
                raise ValueError('invalid error')
        else:
            name = entry['file']
            if not _valid_file(name) or name in files:
                raise ValueError('invalid file')
            files.add(name)
    return sorted(entries, key=lambda entry: entry['slot'])


_SIZE = r'([1-9][0-9]{0,4})\s*[×xX*]\s*([1-9][0-9]{0,4})(?![0-9A-Za-z])'
_OUTPUT_SIZE = re.compile(r'(?:输出|实际)(?:图片|图像)?(?:尺寸|分辨率)?\s*(?:均为|为|是|[:：])?\s*' + _SIZE)
_TARGET_SIZE = re.compile(r'(?:模板|目标|要求)(?:图片|图像)?(?:尺寸|分辨率)?\s*(?:为|是|[:：])?\s*' + _SIZE)


def _skill_reason(error: str) -> tuple[str, str]:
    text = error.lower()
    dimensions = any(word in text for word in ('尺寸', '分辨率', 'dimension', 'resolution'))
    mismatch = any(word in text for word in ('不符', '不匹配', '不一致', '未通过', 'mismatch', 'incorrect'))
    outputs, targets = _OUTPUT_SIZE.findall(error), _TARGET_SIZE.findall(error)
    if mismatch and (dimensions or (outputs and targets)):
        detail = ''
        if len(outputs) == len(targets) == 1:
            output, target = outputs[0], targets[0]
            if output != target and all(int(number) <= 32768 for pair in (output, target) for number in pair):
                detail = f'（输出 {output[0]}×{output[1]}，目标 {target[0]}×{target[1]}）'
        return 'SKILL_DIMENSION_MISMATCH', f'Skill 报告该图尺寸或分辨率不符合要求{detail}；非平台验证结论'
    if any(word in text for word in ('认证失败', '鉴权失败', 'unauthorized', 'authentication failed', 'invalid api key')):
        return 'SKILL_AUTH_FAILED', 'Skill 报告该图处理时认证失败；非平台验证结论'
    if any(word in text for word in ('网络错误', '网络失败', '网络连接失败', '网络超时', '连接超时',
                                     'network error', 'connection refused', 'connection timed out')):
        return 'SKILL_NETWORK_FAILED', 'Skill 报告该图处理时网络连接失败；非平台验证结论'
    if any(word in text for word in ('内容拒绝', '内容被拒绝', '内容政策', '安全策略拒绝',
                                     'content policy', 'safety policy', 'content rejected')):
        return 'SKILL_CONTENT_REJECTED', 'Skill 报告该图处理遭到内容拒绝；非平台验证结论'
    return 'SKILL_REPORTED_FAILURE', 'Skill报告该图处理失败，需核对输入与要求'


def manifest_failure(path: Path, expected_count: int, target: int | None = None,
                     *, allow_windows_fallback: bool = False) -> dict | None:
    """Return Skill-reported failures; missing/unsafe/malformed manifests yield None.

    A target maps the sole local slot back to the original task. The caller must
    preserve storage/publication failures instead of overriding them with this report.
    File references are checked syntactically, never opened or treated as verified images.
    """
    if type(expected_count) is not int or expected_count < 1:
        return None
    if target is not None and (type(target) is not int or target < 0 or expected_count != 1):
        return None
    try:
        raw = _safe_read(path, MAX_MANIFEST_BYTES, allow_windows_fallback=allow_windows_fallback)
        document = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_object)
        entries = _entries(document, expected_count)
    except (OSError, ValueError, TypeError, UnicodeError, RecursionError):
        return None
    errors = []
    for entry in entries:
        if 'error' in entry:
            code, message = _skill_reason(entry['error'])
            errors.append({'slot': entry['slot'] if target is None else target,
                           'code': code, 'message': message})
    if not errors:
        return None
    report = failure_for('all_outputs_failed' if len(errors) == expected_count else 'skill_output_failed',
                         'validating')
    if len(errors) == expected_count:
        report['message'] = 'Skill 报告本轮所有图片处理失败（非平台验证结论）'
    report['slotErrors'] = errors
    return report
