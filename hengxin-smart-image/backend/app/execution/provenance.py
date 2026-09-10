"""Bind collected image bytes to newly appended, native CLI generation events."""

import base64
import binascii
import hashlib
import json
import os
import re
from pathlib import Path

from app.execution.output_collector import OutputCollectionError, _checked
from app.modules.files.validation import MAX_UPLOAD_BYTES, ValidatedImage

MAX_BASE64 = ((MAX_UPLOAD_BYTES + 2) // 3) * 4
MAX_LINE = MAX_BASE64 + 64 * 1024


class ProvenanceError(OutputCollectionError):
    pass


def _logs(home: Path) -> dict[str, Path]:
    home = Path(home).absolute()
    root = _checked(home / 'sessions', home)
    if not root.exists():
        return {}
    if not root.is_dir():
        raise ProvenanceError('invalid_provenance_directory')
    result = {}
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            path = _checked(Path(directory) / name, home)
            if path.is_file():
                if path.stat().st_nlink != 1:
                    raise ProvenanceError('provenance_hardlink_forbidden')
                relative = path.relative_to(root).as_posix()
                if re.fullmatch(r'\d{4}/\d{2}/\d{2}/rollout-[^/]+\.jsonl', relative):
                    result[path.relative_to(home).as_posix()] = path
            elif not path.is_dir():
                raise ProvenanceError('invalid_provenance_file')
    return result


def _prefix(stream, size: int, *, require_newline: bool = False) -> str:
    digest = hashlib.sha256()
    remaining = size
    last = b''
    while remaining:
        chunk = stream.read(min(remaining, 1024 * 1024))
        if not chunk:
            raise ProvenanceError('historical_provenance_changed')
        digest.update(chunk)
        remaining -= len(chunk)
        last = chunk[-1:]
    if require_newline and size and last != b'\n':
        raise ProvenanceError('incomplete_provenance_baseline')
    return digest.hexdigest()


def snapshot_provenance(home: Path) -> dict[str, dict]:
    """Capture all controlled session-log prefixes before starting the CLI."""
    result = {}
    for name, path in _logs(home).items():
        with path.open('rb') as stream:
            size = os.fstat(stream.fileno()).st_size
            result[name] = {'size': size, 'sha256': _prefix(stream, size, require_newline=True)}
    return result


def _events(stream):
    while raw := stream.readline(MAX_LINE + 1):
        if len(raw) > MAX_LINE or not raw.endswith(b'\n'):
            raise ProvenanceError('invalid_provenance_record')
        try:
            event = json.loads(raw)
        except (ValueError, UnicodeError):
            raise ProvenanceError('invalid_provenance_record') from None
        if isinstance(event, dict) and event.get('type') == 'event_msg':
            payload = event.get('payload')
            if isinstance(payload, dict):
                yield payload


def _generation(payload: dict, sid: str, active: set[str]):
    item = payload.get('item')
    if (payload.get('type') != 'item_completed' or not isinstance(item, dict)
            or item.get('type') != 'Extension'
            or item.get('kind') != 'image_gen.generation'):
        return None
    turn = payload.get('turn_id')
    if (payload.get('thread_id') != sid or not isinstance(turn, str)
            or turn not in active):
        raise ProvenanceError('provenance_session_or_turn_mismatch')
    call_id, saved = item.get('id'), item.get('savedPath')
    if (item.get('status') != 'completed' or item.get('failure') is not None
            or not isinstance(call_id, str)
            or not re.fullmatch(r'exec-[A-Za-z0-9_-]+', call_id)
            or not isinstance(saved, str)):
        raise ProvenanceError('invalid_generation_provenance')
    parts = saved.replace('\\', '/').split('/')
    name = call_id + '.png'
    if '..' in parts or parts[-3:] != ['generated_images', sid, name]:
        raise ProvenanceError('provenance_saved_path_mismatch')
    encoded = item.get('result')
    if not isinstance(encoded, str) or len(encoded) > MAX_BASE64:
        raise ProvenanceError('invalid_generation_payload')
    try:
        data = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        raise ProvenanceError('invalid_generation_payload') from None
    if not data or len(data) > MAX_UPLOAD_BYTES:
        raise ProvenanceError('invalid_generation_payload')
    return name, hashlib.sha256(data).hexdigest()


def verify_provenance(
    home: Path, sid: str, baseline: dict, images: list[ValidatedImage],
) -> None:
    if not isinstance(sid, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', sid):
        raise ProvenanceError('invalid_session_id')
    if not isinstance(baseline, dict):
        raise ProvenanceError('invalid_provenance_baseline')
    files = _logs(home)
    if not set(baseline).issubset(files):
        raise ProvenanceError('historical_provenance_changed')
    generations = {}
    for name, path in sorted(files.items()):
        previous = baseline.get(name, {'size': 0, 'sha256': hashlib.sha256(b'').hexdigest()})
        if (not isinstance(previous, dict) or type(previous.get('size')) is not int
                or previous['size'] < 0 or not isinstance(previous.get('sha256'), str)):
            raise ProvenanceError('invalid_provenance_baseline')
        with path.open('rb') as stream:
            if _prefix(stream, previous['size']) != previous['sha256']:
                raise ProvenanceError('historical_provenance_changed')
            if not path.name.endswith('-' + sid + '.jsonl'):
                continue
            active = set()
            for payload in _events(stream):
                kind, turn = payload.get('type'), payload.get('turn_id')
                if kind in ('task_started', 'task_complete'):
                    if (not isinstance(turn, str) or not turn
                            or payload.get('thread_id', sid) != sid):
                        raise ProvenanceError('provenance_session_or_turn_mismatch')
                    if kind == 'task_started':
                        active.add(turn)
                    else:
                        active.discard(turn)
                generation = _generation(payload, sid, active)
                if generation:
                    filename, checksum = generation
                    if filename in generations and generations[filename] != checksum:
                        raise ProvenanceError('conflicting_generation_provenance')
                    generations[filename] = checksum
    if not images or len({image.name for image in images}) != len(images):
        raise ProvenanceError('invalid_provenance_outputs')
    for image in images:
        if (generations.get(image.name) != image.checksum
                or hashlib.sha256(image.data).hexdigest() != image.checksum):
            raise ProvenanceError('image_generation_provenance_missing')
