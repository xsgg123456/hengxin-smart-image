"""Fail-closed Linux process-group inspection for the owning execution node."""
import os
from pathlib import Path


def group_alive(pid, boot):
    if type(pid) is not int or pid <= 1 or not isinstance(boot, str) or not boot:
        raise ValueError('Invalid process group identity')
    if os.name != 'posix' or not Path('/proc/sys/kernel/random/boot_id').is_file():
        raise OSError('Process group verification unavailable')
    if Path('/proc/sys/kernel/random/boot_id').read_text().strip() != boot:
        return False
    for entry in Path('/proc').iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            fields = (entry / 'stat').read_text().rsplit(')', 1)[1].split()
        except (FileNotFoundError, ProcessLookupError):
            continue
        try:
            if fields[0] != 'Z' and int(fields[2]) == pid:
                return True
        except (IndexError, ValueError) as exc:
            raise OSError('Invalid process group data') from exc
    return False
