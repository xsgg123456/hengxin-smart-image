"""Collect only the local images explicitly delivered by this invocation's final reply."""

import json
import re
from io import BytesIO
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from urllib.parse import unquote

from fastapi import HTTPException

from app.execution.diagnostics import _safe_read, _unique_object
from app.execution.events import is_reconnect_notice
from app.execution.output_collector import OutputCollectionError, _checked, _root
from app.modules.files.validation import MAX_UPLOAD_BYTES, ValidatedImage, validate_image

MAX_EVENTS_BYTES = 64 * 1024 * 1024
_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}
_PROTECTED = {'inputs', 'targets', 'original', 'current', 'skills', '.agents', '.codex'}
_DIGITS = r'[0-9零一二三四五六七八九十]+'
_NUMBER = re.compile(r'(?:主图|图片|图)\s*[（(]?\s*(' + _DIGITS + r')|第\s*(' + _DIGITS + r')\s*张')
_ORDERED = re.compile(r'^(' + _DIGITS + r')\s*[.、)）]\s*')


def _number(value: str) -> int:
    if value.isascii() and value.isdecimal():
        return int(value)
    digits = dict(zip('零一二三四五六七八九', range(10)))
    if value in digits:
        return digits[value]
    parts = value.split('十')
    if len(parts) == 2 and all(not part or part in digits for part in parts):
        return digits.get(parts[0], 1) * 10 + digits.get(parts[1], 0)
    raise OutputCollectionError('invalid_final_reply')


def _numbers(text: str) -> set[int]:
    numbers = {_number(a or b) for a, b in _NUMBER.findall(text)}
    plain = text.strip(' *()（）')
    if re.fullmatch(_DIGITS, plain):
        numbers.add(_number(plain))
    return numbers


def _context_numbers(prefix: str) -> set[int]:
    # Read the nearest numbered heading/list between this and the prior link.
    # Suffixes and intervening explanation do not erase an explicit image number.
    for line in reversed(prefix.splitlines()):
        line = line.strip()
        heading = line.startswith('#')
        clean = re.sub(r'^#{1,6}\s*', '', line).strip('* ')
        ordered = _ORDERED.match(clean)
        if ordered:
            return {_number(ordered[1])} | _numbers(clean[ordered.end():])
        if _NUMBER.match(clean) or heading:
            return _numbers(clean)
    return set()


def _final_text(events: Path, session_id: str) -> str:
    try:
        raw = _safe_read(events, MAX_EVENTS_BYTES, allow_windows_fallback=True)
        previous, last = None, None
        completed = False
        for line in raw.decode('utf-8').splitlines():
            if not line.strip():
                continue
            event = json.loads(line, object_pairs_hook=_unique_object)
            if not isinstance(event, dict) or not isinstance(event.get('type'), str):
                raise ValueError
            if event['type'] == 'thread.started' and event.get('thread_id') != session_id:
                raise OutputCollectionError('session_mismatch')
            if event['type'] == 'turn.failed':
                raise ValueError
            if event['type'] == 'error':
                if completed or not is_reconnect_notice(event):
                    raise ValueError
            if event['type'] == 'turn.completed':
                completed = True
            previous, last = last, event
    except OutputCollectionError:
        raise
    except OSError:
        raise OutputCollectionError('unreadable_event_stream') from None
    except (ValueError, UnicodeError, RecursionError):
        raise OutputCollectionError('invalid_event_stream') from None
    # A tool/command after an earlier agent message invalidates that message as
    # a final delivery. Never search backwards through an invocation for images.
    if not last or last['type'] != 'turn.completed' or not previous:
        raise OutputCollectionError('final_reply_missing')
    item = previous.get('item')
    if (previous['type'] != 'item.completed' or not isinstance(item, dict)
            or item.get('type') != 'agent_message' or not isinstance(item.get('text'), str)
            or not item['text'].strip()):
        raise OutputCollectionError('final_reply_missing')
    return item['text']


def _without_code(text: str) -> str:
    lines, fence = [], None
    for line in text.splitlines(keepends=True):
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})', line)
        if marker:
            token = marker[1]
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            lines.append('\n')
        elif fence or line.startswith(('    ', '\t')):
            lines.append('\n')
        else:
            lines.append(line)
    return re.sub(r'(`+)[^`]*?\1', '', ''.join(lines))


def _links(text: str) -> list[tuple[str, str, int | None]]:
    text = _without_code(text)
    result, end = [], 0
    pattern = re.compile(r'(?<!\\)(!?)(\[[^\[\]\n]*\])\(')
    while match := pattern.search(text, end):
        previous_end = end
        start, cursor, depth = match.end(), match.end(), 1
        angle = text[start:start + 1] == '<'
        while cursor < len(text):
            char = text[cursor]
            if char == '\\':
                cursor += 2
                continue
            if angle:
                if char == '>':
                    angle = False
            elif char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
                if depth == 0:
                    break
            cursor += 1
        if depth:
            raise OutputCollectionError('invalid_final_reply')
        target = text[start:cursor].strip()
        end = cursor + 1
        # Optional Markdown title is metadata, never part of a file path.
        target = re.sub(r'\s+[\"\'][^\"\']*[\"\']$', '', target).strip()
        if target.startswith('<') and target.endswith('>'):
            target = target[1:-1]
        target = re.sub(r'\\([() ])', r'\1', target)
        try:
            target = unquote(target, errors='strict')
        except UnicodeError:
            raise OutputCollectionError('invalid_final_reply') from None
        if PurePosixPath(target).suffix.lower() not in _EXTENSIONS:
            if match[1]:
                raise OutputCollectionError('invalid_output_image')
            continue
        label = match[2][1:-1]
        numbers = _context_numbers(text[previous_end:match.start()]) | _numbers(label)
        if len(numbers) > 1:
            raise OutputCollectionError('invalid_final_reply')
        result.append((label, target, next(iter(numbers), None)))
    return result


def _unique_links(links):
    """One image preview plus its download link is one delivery, not two outputs."""
    unique = {}
    for label, target, number in links:
        logical = PurePosixPath(target)
        key = str(logical if logical.is_absolute() else PurePosixPath('/work') / logical)
        previous = unique.get(key)
        if previous:
            old_number = previous[2]
            if old_number is not None and number is not None and old_number != number:
                raise OutputCollectionError('invalid_final_reply')
            number = old_number if old_number is not None else number
        unique[key] = (label, target, number)
    return list(unique.values())


def _local_file(target: str, work: Path, home: Path, root: Path,
                known_files: dict[str, str]) -> tuple[Path, Path]:
    if (not target or any(ord(char) < 32 or ord(char) == 127 for char in target)
            or any(char in target for char in '\\:?#') or target.startswith('//')):
        raise OutputCollectionError('output_path_escape')
    logical = PurePosixPath(target)
    if any(part in {'.', '..'} for part in target.split('/')):
        raise OutputCollectionError('output_path_escape')
    native = PurePosixPath('/home/runner/.codex/generated_images') / root.name
    if logical.is_relative_to(native):
        relative, boundary = logical.relative_to(native), home
        path = root.joinpath(*relative.parts)
        if relative.as_posix() in known_files:
            raise OutputCollectionError('historical_output_forbidden')
    else:
        if logical.is_relative_to('/work'):
            relative = logical.relative_to('/work')
        elif not logical.is_absolute():
            relative = logical
        else:
            raise OutputCollectionError('output_path_escape')
        if any(part in _PROTECTED for part in relative.parts):
            raise OutputCollectionError('output_path_escape')
        path, boundary = work.joinpath(*relative.parts), work
    path = _checked(path, boundary)
    try:
        if not path.is_file():
            raise OutputCollectionError('invalid_output_file')
        if path.stat().st_nlink != 1:
            raise OutputCollectionError('output_hardlink_forbidden')
    except OSError:
        raise OutputCollectionError('invalid_output_file') from None
    return path, boundary


def collect_final_outputs(
    work: Path, home: Path, events: Path, session_id: str,
    known_files: dict[str, str], expected_count: int,
) -> list[ValidatedImage]:
    """Require an exact, unambiguous delivery; unrelated generated candidates are ignored."""
    if type(expected_count) is not int or expected_count < 1:
        raise OutputCollectionError('invalid_output_count')
    root = _root(Path(home), session_id)
    links = _unique_links(_links(_final_text(Path(events), session_id)))
    if not links:
        raise OutputCollectionError('final_reply_missing')
    if len(links) != expected_count:
        raise OutputCollectionError('final_output_count_mismatch')
    numbers = [number for _, _, number in links]
    if any(number is not None for number in numbers):
        # A single-image revision may retain its original task number (e.g. 主图4).
        valid_single = expected_count == 1 and numbers[0] > 0
        if not valid_single and set(numbers) != set(range(1, expected_count + 1)):
            raise OutputCollectionError('invalid_final_reply')
        links.sort(key=lambda item: item[2])
    images, seen = [], set()
    for _, target, _ in links:
        path, _ = _local_file(target, Path(work), Path(home), root, known_files)
        identity = path.resolve()
        if identity in seen:
            raise OutputCollectionError('invalid_final_reply')
        seen.add(identity)
        try:
            data = _safe_read(path, MAX_UPLOAD_BYTES, allow_windows_fallback=True)
        except (OSError, ValueError):
            raise OutputCollectionError('invalid_output_file') from None
        try:
            images.append(validate_image(SimpleNamespace(
                file=BytesIO(data), filename=path.name, content_type=None,
            )))
        except HTTPException:
            raise OutputCollectionError('invalid_output_image') from None
    return images
