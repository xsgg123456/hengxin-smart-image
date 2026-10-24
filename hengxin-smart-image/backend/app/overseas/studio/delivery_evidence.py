"""Bridge final native presentations without discovering output files."""
import logging
from pathlib import PurePosixPath

from .native_images import read_current, read_history

UNREADABLE = '自动识别未找到可确认的输出，请通过“取回文件”选择尚存原件。'


def evidence(workspace, summary, links):
    cursor = getattr(workspace, 'native_cursor', None)
    end = getattr(workspace, 'native_end_cursor', None)
    prefix = PurePosixPath('/home/runner/.codex/generated_images') / summary.session_id
    targets = {target for _, target in links if target and PurePosixPath(target).is_relative_to(prefix)}
    proven = {}
    if links:
        # Explicit final references establish selection. Unrelated generation or
        # display records must never prevent collecting ordinary work images.
        for target in targets:
            relative = PurePosixPath(target).relative_to(prefix).as_posix()
            checksum = getattr(workspace, 'baseline', {}).get(relative)
            if checksum:
                proven[target] = checksum
        if targets and cursor is not None:
            try:
                proven.update(read_history(workspace.home, summary.session_id, targets, end))
            except (OSError, ValueError, TypeError, RecursionError):
                logging.getLogger(__name__).warning('Studio optional native digest evidence unavailable')
        return [], proven, []
    if cursor is None:
        return [], {}, []
    try:
        current = read_current(workspace.home, summary.session_id, cursor, summary.final_text, end)
        return current, {row['path']: row['checksum'] for row in current}, []
    except (OSError, ValueError, TypeError, RecursionError):
        logging.getLogger(__name__).warning('Studio native delivery evidence rejected')
        return [], {}, [UNREADABLE]
