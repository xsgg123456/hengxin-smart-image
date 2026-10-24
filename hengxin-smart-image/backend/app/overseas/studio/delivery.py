"""Collect images from the completed final reply, never by scanning output files."""
from io import BytesIO
from pathlib import PurePosixPath
import re
from types import SimpleNamespace
from urllib.parse import unquote

from fastapi import HTTPException
from markdown_it import MarkdownIt

from app.execution.delivery_markdown import _legacy_space_paths
from app.execution.diagnostics import _safe_read
from app.execution.final_delivery import _local_file, _PROTECTED
from app.execution.output_collector import OutputCollectionError, _root
from app.modules.files.validation import MAX_UPLOAD_BYTES, validate_image
from .delivery_evidence import evidence

EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}
INVALID_REFERENCE = '一张最终回复图片未通过文件或归属校验，文字回复已保留。'


def references(text):
    """Rendered images and image downloads need no heading or delivery wording."""
    parser = MarkdownIt('commonmark')
    parser.validateLink = lambda _url: True  # Validated locally, never fetched.
    for token in parser.parse(_legacy_space_paths(text)):
        if token.type != 'inline':
            continue
        for child in token.children or []:
            target = (child.attrGet('src') if child.type == 'image' else
                      child.attrGet('href') if child.type == 'link_open' else None)
            if target is None:
                continue
            try:
                decoded = unquote(target, errors='strict')
            except UnicodeError:
                yield target, None
                continue
            logical = decoded.removeprefix('sandbox:')
            if PurePosixPath(logical).suffix.lower() in EXTENSIONS:
                yield decoded, logical
            elif child.type == 'image':
                yield decoded, None


def _canonical(logical, session_id):
    """Validate ownership without opening a file, so missing files stay expected."""
    if (not isinstance(logical, str) or not logical
            or any(ord(char) < 32 or ord(char) == 127 for char in logical)
            or any(char in logical for char in '\\:?#') or logical.startswith('//')
            or any(part in ('.', '..') for part in logical.split('/'))):
        raise OutputCollectionError('invalid_image_reference')
    path = PurePosixPath(logical)
    native = PurePosixPath('/home/runner/.codex/generated_images') / session_id
    if path.is_relative_to(native):
        return str(path)
    if not path.is_absolute():
        path = PurePosixPath('/work') / path
    if not path.is_relative_to('/work') or any(
            part in _PROTECTED for part in path.relative_to('/work').parts):
        raise OutputCollectionError('output_path_escape')
    return str(path)


def enumerate_delivery(workspace, summary):
    """Return unique expected references, optional digests and selection warnings.

    No image file is opened here. A missing or unreadable selected file still
    contributes one expected output for durable capture and later recovery.
    """
    if not summary.turn_completed or summary.error or summary.final_text is None:
        return [], {}, []
    try:
        from .native_rollout import session
        session(summary.session_id)
        links = list(references(summary.final_text))
    except (ValueError, OSError, TypeError, RecursionError):
        return [], {}, ['最终回复图片的引用无法读取，文字回复已保留。']
    selected, seen, warnings = [], set(), []
    for _, logical in links:
        try:
            canonical = _canonical(logical, summary.session_id)
        except (OutputCollectionError, TypeError, ValueError):
            warnings.append(INVALID_REFERENCE)
            continue
        if canonical not in seen:
            seen.add(canonical)
            selected.append((canonical, canonical))
    # Normalize before digest lookup too: alternate spellings cannot bypass
    # checksum evidence. An invalid explicit list never triggers native fallback.
    if links:
        if selected:
            _, proven, evidence_warnings = evidence(workspace, summary, selected)
            warnings.extend(evidence_warnings)
        else:
            proven = {}
    else:
        native, proven, evidence_warnings = evidence(workspace, summary, [])
        warnings.extend(evidence_warnings)
        selected = [(row['path'], row['path']) for row in native]
    if not links and not selected and not warnings and re.search(
            r'已(?:成功)?生成[^。\n]{0,50}(?:图|image)|'
            r'(?:image|picture)s?\s+(?:has|have|was|were)\s+(?:been\s+)?generated',
            summary.final_text, re.I):
        warnings.append('本轮回复称已生成图片，但未收到可验证的图片交付；请联系管理员核查，无需重新生成。')
    return selected, proven, warnings


def collect_reference(workspace, summary, target, logical, proven):
    """Read one selected file; callers can persist successes and retry failures."""
    if not summary.turn_completed or summary.error:
        raise OutputCollectionError('final_delivery_uncertain')
    canonical = _canonical(logical, summary.session_id)
    root = _root(workspace.home / '.codex', summary.session_id)
    path, _ = _local_file(canonical, workspace.work, workspace.home / '.codex', root, {})
    data = _safe_read(path, MAX_UPLOAD_BYTES, allow_windows_fallback=True)
    image = validate_image(SimpleNamespace(file=BytesIO(data), filename=path.name,
                                          content_type=None))
    if canonical in proven and image.checksum != proven[canonical]:
        raise OutputCollectionError('native_image_checksum_mismatch')
    return image


def collect_delivery(workspace, summary):
    """Compatibility wrapper: valid final images plus per-reference warnings."""
    links, proven, warnings = enumerate_delivery(workspace, summary)
    delivered = []
    for target, logical in links:
        try:
            delivered.append((target, collect_reference(workspace, summary, target, logical, proven)))
        except (OutputCollectionError, HTTPException, OSError, ValueError):
            warnings.append(INVALID_REFERENCE)
    return delivered, warnings
