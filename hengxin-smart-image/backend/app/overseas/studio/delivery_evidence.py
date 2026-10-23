"""Bridge explicit native image presentations without discovering output files."""
import logging
from pathlib import PurePosixPath

from .native_images import read_current, read_history

UNREADABLE = '原生图片交付记录校验失败，文字已保留；请联系管理员补收，无需重新生成。'


def evidence(workspace, summary, links):
    current, proven, warnings = [], {}, []
    cursor = getattr(workspace, 'native_cursor', None)
    if cursor is not None:
        try:
            current = read_current(workspace.home, summary.session_id, cursor, summary.final_text)
            proven.update({row['path']: row['checksum'] for row in current})
        except (OSError, ValueError, TypeError, RecursionError):
            logging.getLogger(__name__).warning('Studio native delivery evidence rejected')
            warnings.append(UNREADABLE)
    prefix = PurePosixPath('/home/runner/.codex/generated_images') / summary.session_id
    historical = set()
    for _, target in links:
        if target and PurePosixPath(target).is_relative_to(prefix):
            relative = PurePosixPath(target).relative_to(prefix).as_posix()
            if relative in workspace.baseline:
                historical.add(target)
    if historical and cursor is not None:
        try:
            proven.update(read_history(workspace.home, summary.session_id, historical))
        except (OSError, ValueError, TypeError, RecursionError):
            logging.getLogger(__name__).warning('Studio historical delivery evidence rejected')
            warnings.append(UNREADABLE)
    return current, proven, warnings
