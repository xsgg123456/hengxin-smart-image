"""Bounded, link-free reads of one native Codex session rollout."""
import json
import os
import re
from pathlib import Path

from . import context_fs as fs

MAX_LINE = 64 * 1024 * 1024
MAX_TOTAL = 512 * 1024 * 1024


def session(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', value):
        raise ValueError('Invalid native session ID')
    return value


def locate(home, session_id):
    session(session_id)
    root = fs.checked(Path(home) / '.codex' / 'sessions', missing=True, directory=True)
    if not root.exists():
        return None
    matches = []
    for current, directories, files in os.walk(root, followlinks=False):
        fs.checked(Path(current), directory=True)
        for name in directories:
            fs.checked(Path(current) / name, directory=True)
        for name in files:
            if name.startswith('rollout-') and name.endswith(f'-{session_id}.jsonl'):
                matches.append(fs.checked(Path(current) / name, directory=False))
                if len(matches) > 1:
                    raise ValueError('Ambiguous native session rollout')
    return matches[0] if matches else None


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate native rollout JSON field')
        result[key] = value
    return result


def line(stream, budget):
    raw = stream.readline(min(MAX_LINE, MAX_TOTAL - budget[0]) + 1)
    budget[0] += len(raw)
    if budget[0] > MAX_TOTAL:
        raise ValueError('Native rollout read exceeds 512 MiB limit')
    if len(raw) > MAX_LINE:
        raise ValueError('Native rollout line exceeds 64 MiB limit')
    if not raw:
        return None
    if not raw.endswith(b'\n'):
        raise ValueError('Truncated native rollout line')
    try:
        value = json.loads(raw, object_pairs_hook=_pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, UnicodeError, RecursionError):
        raise ValueError('Invalid native rollout JSON') from None
    if not isinstance(value, dict):
        raise ValueError('Invalid native rollout record')
    return value


def header(stream, session_id, budget):
    value = line(stream, budget)
    if (not value or value.get('type') != 'session_meta'
            or not isinstance(value.get('payload'), dict)
            or value['payload'].get('id') != session_id):
        raise ValueError('Native rollout session mismatch')


def snapshot(home: Path, session_id: str | None) -> dict:
    if session_id is None:
        return {}
    path = locate(home, session_id)
    if path is None:
        raise ValueError('Native session rollout is missing')
    with fs.reader(path) as stream:
        header(stream, session_id, [0])
        info = os.fstat(stream.fileno())
        stream.seek(-1, os.SEEK_END)
        if stream.read(1) != b'\n':
            raise ValueError('Truncated native rollout')
        # relative_to also handles Windows extended-length paths returned by checked.
        root = fs.checked(Path(home), directory=True)
        return {'path': path.relative_to(root).as_posix(), 'offset': info.st_size,
                'dev': info.st_dev, 'ino': info.st_ino}


def _offset(stream, path, home, cursor, minimum):
    root = fs.checked(Path(home), directory=True)
    info = os.fstat(stream.fileno())
    offset = cursor.get('offset')
    if (cursor.get('path') != path.relative_to(root).as_posix()
            or (cursor.get('dev'), cursor.get('ino')) != (info.st_dev, info.st_ino)
            or type(offset) is not int or not minimum <= offset <= info.st_size):
        raise ValueError('Native rollout identity or cursor changed')
    position = stream.tell()
    stream.seek(offset - 1)
    if stream.read(1) != b'\n':
        raise ValueError('Native rollout cursor is not a line boundary')
    stream.seek(position)
    return offset


def records(home, session_id, cursor=None, end_cursor=None, *, first_turn_only=False):
    path = locate(home, session_id)
    if path is None:
        if cursor or end_cursor:
            raise ValueError('Native session rollout is missing')
        return
    terminal = None
    with fs.reader(path) as stream:
        budget = [0]
        header(stream, session_id, budget)
        start = _offset(stream, path, home, cursor, stream.tell()) if cursor else stream.tell()
        end = (_offset(stream, path, home, end_cursor, start) if end_cursor
               else os.fstat(stream.fileno()).st_size)
        stream.seek(start)
        while stream.tell() < end:
            value = line(stream, budget)
            if value is None or stream.tell() > end:
                raise ValueError('Native rollout end boundary changed')
            if value.get('type') == 'session_meta':
                raise ValueError('Duplicate native rollout session metadata')
            payload = value.get('payload')
            if (first_turn_only and value.get('type') == 'event_msg'
                    and isinstance(payload, dict) and payload.get('type') == 'task_complete'):
                terminal = value
                break
            yield value
    # Exit the safe-reader context normally before publishing completion so
    # replacement/mtime/link checks still run when a caller stops at this turn.
    if terminal is not None:
        yield terminal
