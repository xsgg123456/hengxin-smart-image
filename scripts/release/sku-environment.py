"""Read one root-only credential; never log it or change the existing Compose files."""
import os
from pathlib import Path
import stat

KEY = 'OVERSEAS_DESIGN_API_KEY'


def credential(path):
    path = Path(path)
    if not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents)):
        raise RuntimeError('Credential must be an absolute regular private path')
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o600:
        raise RuntimeError('Credential must be root-owned mode 0600')
    if not 1 <= info.st_size <= 4096:
        raise RuntimeError('Invalid credential size')
    value = path.read_text().strip()
    if not value or any(c.isspace() or ord(c) < 32 for c in value):
        raise RuntimeError('Credential must contain exactly one nonempty token')
    return value


def overlay(image, value):
    return {'services': {'api': {'image': image, 'environment': {KEY: value}}}}


def expected_environment(items, value):
    previous = [item for item in items if not item.startswith(KEY+'=')]
    # No environment other than the explicitly authorized new credential can change.
    return previous + [KEY+'='+value]
