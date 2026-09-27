"""Collect only the local images explicitly delivered by this invocation's final reply."""

from io import BytesIO
from pathlib import Path, PurePosixPath
from types import SimpleNamespace

from fastapi import HTTPException

from app.execution.diagnostics import _safe_read
from app.execution.events import parse_events
from app.execution.output_collector import OutputCollectionError, _checked, _root
from app.modules.files.validation import MAX_UPLOAD_BYTES, ValidatedImage, validate_image

from app.execution.delivery_markdown import delivery_links as _links

_PROTECTED = {'inputs', 'targets', 'original', 'current', 'skills', '.agents', '.codex'}


def _final_text(events: Path, session_id: str) -> str:
    summary = parse_events(events, session_id)
    if summary.error and summary.error != 'cli_error':
        raise OutputCollectionError(summary.error)
    if not summary.session_id or not summary.turn_completed:
        raise OutputCollectionError('final_delivery_uncertain')
    if not summary.final_text:
        raise OutputCollectionError('final_reply_missing')
    return summary.final_text

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
