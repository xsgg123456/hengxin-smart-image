"""Collect immutable new output files after the invocation has stopped."""

import hashlib
import json
import re
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException

from app.modules.files.validation import MAX_UPLOAD_BYTES, ValidatedImage, validate_image


class OutputCollectionError(ValueError):
    pass


def _checked(path: Path, boundary: Path) -> Path:
    path = path.absolute()
    boundary = boundary.absolute()
    if not path.is_relative_to(boundary):
        raise OutputCollectionError('output_path_escape')
    for part in (path, *path.parents):
        if part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction()):
            raise OutputCollectionError('output_link_forbidden')
        if part == boundary:
            break
    if not path.resolve().is_relative_to(boundary.resolve()):
        raise OutputCollectionError('output_path_escape')
    return path


def _root(home: Path, session_id: str) -> Path:
    if not isinstance(session_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', session_id):
        raise OutputCollectionError('invalid_session_id')
    return _checked(Path(home) / 'generated_images' / session_id, Path(home))


def _files(root: Path) -> dict[str, Path]:
    if not root.exists():
        return {}
    if not root.is_dir():
        raise OutputCollectionError('invalid_output_directory')
    result = {}
    for path in root.rglob('*'):
        _checked(path, root)
        if path.is_file():
            if path.stat().st_nlink != 1:
                raise OutputCollectionError('output_hardlink_forbidden')
            result[path.relative_to(root).as_posix()] = path
        elif not path.is_dir():
            raise OutputCollectionError('invalid_output_file')
    return result


def _digest(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def snapshot_outputs(home: Path, session_id: str) -> dict[str, str]:
    """Must run before launch; save this snapshot durably for recovery."""
    return {name: _digest(path) for name, path in _files(_root(home, session_id)).items()}


def _manifest(path: Path, root: Path, count: int, allow_partial: bool) -> list[str | None]:
    # An explicit per-round manifest can live outside generated_images, but its
    # referenced files must always be relative to this exact session directory.
    if any(part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction())
           for part in (path, *path.parents)):
        raise OutputCollectionError('manifest_link_forbidden')
    try:
        if path.stat().st_size > 64 * 1024:
            raise ValueError
        document = json.loads(path.read_text(encoding='utf-8'))
        entries = document['outputs']
        if not isinstance(entries, list) or len(entries) != count:
            raise ValueError
        slots = {}
        for entry in entries:
            slot = entry['slot']
            if type(slot) is not int or not 0 <= slot < count or slot in slots:
                raise ValueError
            if allow_partial and 'error' in entry and 'file' not in entry:
                if not isinstance(entry['error'], str) or not entry['error'].strip() or len(entry['error']) > 1000:
                    raise ValueError
                slots[slot] = None
                continue
            if 'error' in entry:
                raise ValueError
            name = entry['file']
            if not isinstance(name, str) or not name or '\\' in name or ':' in name:
                raise ValueError
            relative = Path(name)
            if relative.is_absolute() or any(part in ('.', '..') for part in name.split('/')):
                raise ValueError
            _checked(root / relative, root)
            slots[slot] = relative.as_posix()
        ordered = [slots[slot] for slot in range(count)]
        successful = [name for name in ordered if name is not None]
        if len(set(successful)) != len(successful):
            raise ValueError
        return ordered
    except (OSError, ValueError, TypeError, KeyError, UnicodeError):
        raise OutputCollectionError('invalid_output_manifest') from None


def collect_outputs(
    home: Path, session_id: str, known_files: dict[str, str], expected_count: int,
    manifest_path: Path | None = None,
    *, allow_partial: bool = False,
) -> list[ValidatedImage | None]:
    if type(expected_count) is not int or expected_count < 1:
        raise OutputCollectionError('invalid_output_count')
    root = _root(home, session_id)
    files = _files(root)
    for name, checksum in known_files.items():
        if name not in files or _digest(files[name]) != checksum:
            raise OutputCollectionError('historical_output_changed')
    new_files = {name: path for name, path in files.items() if name not in known_files}
    manifest = Path(manifest_path) if manifest_path is not None else root / 'manifest.json'
    if manifest.exists():
        if manifest.absolute().is_relative_to(root.absolute()):
            name = manifest.absolute().relative_to(root.absolute()).as_posix()
            if name in known_files:
                raise OutputCollectionError('historical_manifest_forbidden')
            new_files.pop(name, None)
        names = _manifest(manifest, root, expected_count, allow_partial)
    elif manifest_path is not None or expected_count > 1:
        raise OutputCollectionError('output_manifest_required')
    else:
        names = list(new_files)
    if len(names) != expected_count or {name for name in names if name is not None} != set(new_files):
        raise OutputCollectionError('output_count_or_manifest_mismatch')
    images = []
    for name in names:
        if name is None:
            images.append(None)
            continue
        path = _checked(new_files[name], root)
        with path.open('rb') as stream:
            data = stream.read(MAX_UPLOAD_BYTES + 1)
        try:
            images.append(validate_image(SimpleNamespace(
                file=BytesIO(data), filename=path.name, content_type=None,
            )))
        except HTTPException:
            raise OutputCollectionError('invalid_output_image') from None
    return images
