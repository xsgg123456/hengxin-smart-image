"""Strict durable review credentials and single-writer state transactions."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
import time

from review_files import git_snapshot, identity, safe_path

HEX = re.compile(r'[0-9a-f]{64}')
ENTRY = re.compile(r'(100644|100755|120000):[0-9a-f]{64}')
LOCK_TIMEOUT = 2.0
LOCK_POLL_INTERVAL = 0.05


def require(condition, message='审查状态结构损坏，请恢复有效凭据后重试'):
    if not condition:
        raise ValueError(message)


def keys(value, expected):
    require(isinstance(value, dict) and set(value) == set(expected))


def path_name(name):
    require(isinstance(name, str) and bool(name) and '\\' not in name)
    p = PurePosixPath(name)
    require(not p.is_absolute() and '..' not in p.parts and ':' not in name)


def snap(value):
    keys(value, ('id', 'files'))
    require(isinstance(value['files'], dict))
    for name, digest in value['files'].items():
        path_name(name)
        require(isinstance(digest, str) and ENTRY.fullmatch(digest) is not None)
    require(isinstance(value['id'], str) and value['id'] == identity(value['files']))


def report(root, name):
    require(isinstance(name, str) and bool(name), '必须提供仓库内审查报告路径')
    path = Path(name)
    path = path if path.is_absolute() else root / path
    try:
        relative = path.relative_to(root)
        path_name(relative.as_posix())
        path = safe_path(root, relative.as_posix())
        require(not path.is_symlink() and path.is_file(), '审查报告必须是仓库内真实文件')
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError('审查报告必须是仓库内真实文件') from exc
    raw = path.read_bytes()
    require(bool(raw.strip()), '审查报告不能为空')
    return {'path': relative.as_posix(), 'sha256': hashlib.sha256(raw).hexdigest()}


def validate(root, state, *, verify_report=True):
    keys(state, ('schema', 'baseline', 'candidate', 'approved', 'checkpoint'))
    require(type(state['schema']) is int and state['schema'] == 1)
    snap(state['baseline'])
    if state['candidate'] is not None:
        snap(state['candidate'])
    approved = state['approved']
    if approved is not None:
        keys(approved, ('snapshot', 'report', 'stage1', 'stage2'))
        snap(approved['snapshot'])
        require(approved['stage1'] == approved['stage2'] == 'PASS')
        keys(approved['report'], ('path', 'sha256'))
        path_name(approved['report']['path'])
        require(isinstance(approved['report']['sha256'], str) and HEX.fullmatch(approved['report']['sha256']) is not None)
        if verify_report:
            try:
                valid = report(root, approved['report']['path']) == approved['report']
            except (OSError, ValueError):
                valid = False
            require(valid, '审查报告已修改或凭据失效，请重新执行 review-prepare 和两阶段审查')
    checkpoint = state['checkpoint']
    if checkpoint is not None:
        keys(checkpoint, ('id', 'reason', 'used'))
        require(isinstance(checkpoint['id'], str) and HEX.fullmatch(checkpoint['id']) is not None)
        require(isinstance(checkpoint['reason'], str) and bool(checkpoint['reason'].strip()))
        require(type(checkpoint['used']) is bool)


def package(files):
    return {'id': identity(files), 'files': files}


def write(path, state):
    descriptor, temporary = tempfile.mkstemp(prefix='review-state.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as stream:
            json.dump(state, stream, ensure_ascii=True, sort_keys=True)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def transaction(root, *, verify_report=True, verify_final_report=True):
    root = Path(root).resolve()
    directory = root / '.codex'
    require(not directory.is_symlink(), '.codex 不得为符号链接')
    try:
        directory.resolve().relative_to(root)
    except ValueError as exc:
        raise ValueError('.codex 不得指向仓库外目录') from exc
    directory.mkdir(exist_ok=True)
    lock = directory / '.review-state.lock'
    deadline = time.monotonic() + LOCK_TIMEOUT
    while True:
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            break
        except FileExistsError as exc:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError('审查状态锁等待超时：若进程已崩溃，确认后移除 .codex/.review-state.lock') from exc
            time.sleep(min(LOCK_POLL_INTERVAL, remaining))
    try:
        os.close(descriptor)
        path = directory / 'review-state.json'
        require(not path.is_symlink(), '审查状态不得为符号链接')
        if path.exists():
            state = json.loads(path.read_text(encoding='utf-8'))
            validate(root, state, verify_report=verify_report)
        else:
            state = {'schema': 1, 'baseline': package(git_snapshot(root, 'HEAD')),
                     'candidate': None, 'approved': None, 'checkpoint': None}
            write(path, state)
        yield state
        validate(root, state, verify_report=verify_final_report)
        write(path, state)
    finally:
        lock.unlink()


def read(root):
    """Read one atomically published state without locks or filesystem writes."""
    root = Path(root).resolve()
    path = safe_path(root, '.codex/review-state.json')
    require(not path.is_symlink(), '审查状态不得为符号链接')
    if path.exists():
        state = json.loads(path.read_text(encoding='utf-8'))
    else:
        state = {'schema': 1, 'baseline': package(git_snapshot(root, 'HEAD')),
                 'candidate': None, 'approved': None, 'checkpoint': None}
    validate(root, state)
    return state
