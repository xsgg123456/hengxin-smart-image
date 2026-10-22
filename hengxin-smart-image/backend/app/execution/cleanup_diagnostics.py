"""Stable cleanup failure codes and stack locations without exception payloads."""
import errno
import json
import logging
from pathlib import Path
import re
import traceback
from uuid import UUID

from sqlalchemy.exc import DBAPIError, IntegrityError
from .cleanup_paths import CleanupSafetyError

logger = logging.getLogger(__name__)
APP = Path(__file__).resolve().parents[1]
SAFETY_CODES = frozenset({'UNEXPECTED_LINK', 'CROSS_DEVICE', 'NON_PRIVATE_MATERIAL',
                         'UNSAFE_REMOVAL', 'ROOT_INVALID', 'TARGET_CHANGED'})
STAGES = frozenset({'history_filesystem', 'cache_filesystem', 'history_database',
                   'history_receipt', 'cache_receipt', 'object_remove',
                   'resource_scan', 'scan', 'worker_loop', 'worker_lifecycle', 'task_delete'})


class ThumbnailOwnershipUnresolved(RuntimeError):
    """The thumbnail executor still owns material; preserve it and retry later."""


def code(error, stage):
    if isinstance(error, CleanupSafetyError):
        return 'CLEANUP_' + error.code if error.code in SAFETY_CODES else 'CLEANUP_SAFETY_BLOCKED'
    if isinstance(error, ThumbnailOwnershipUnresolved):
        return 'CLEANUP_THUMBNAIL_BUSY'
    if isinstance(error, PermissionError):
        return 'CLEANUP_PERMISSION_DENIED'
    if isinstance(error, DBAPIError):
        state = getattr(error.orig, 'sqlstate', None) or getattr(error.orig, 'pgcode', None)
        if state in ('55P03', '40P01', '40001'):
            return 'CLEANUP_DATABASE_BUSY'
        return 'CLEANUP_DATABASE_CONSTRAINT' if isinstance(error, IntegrityError) else 'CLEANUP_DATABASE_FAILED'
    if stage == 'object_remove':
        return 'CLEANUP_OBJECT_STORAGE_FAILED'
    if isinstance(error, OSError):
        return 'CLEANUP_IO_FAILED'
    return 'CLEANUP_UNEXPECTED_FAILURE'


def locations(error):
    result = []
    for frame, line in traceback.walk_tb(error.__traceback__):
        try:
            relative = Path(frame.f_code.co_filename).resolve().relative_to(APP).as_posix()
        except (OSError, ValueError):
            continue
        if re.fullmatch(r'[a-zA-Z0-9_/]+\.py', relative):
            result.append({'module': relative, 'line': line})
    return result[-8:]


def report(error, *, stage, resource_id):
    stage = stage if stage in STAGES else 'worker_loop'
    try:
        identifier = str(UUID(str(resource_id)))
    except (ValueError, TypeError, AttributeError):
        identifier = 'unknown'
    name = type(error).__name__
    payload = dict(event='cleanup_deferred', stage=stage, resourceId=identifier,
                   code=code(error, stage), errorType=name if re.fullmatch('[A-Za-z_]{1,64}', name) else 'Exception',
                   locations=locations(error))
    if isinstance(error, OSError) and error.errno in errno.errorcode:
        payload['osCode'] = errno.errorcode[error.errno]
    # No str(error), SQL parameters, paths, exception chains or frame locals.
    logger.error('cleanup_deferred %s', json.dumps(payload, separators=(',', ':')))
    return payload['code']
