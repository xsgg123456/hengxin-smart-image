"""Trusted local sampler. All three physical paths must be explicitly supplied."""
from pathlib import Path
import shutil

from sqlalchemy import select

from app.models import utcnow
from .admission import gate, pending_bytes
from .models import CapacityReservation

ROLES = {'execution', 'objects', 'database'}


def inspect_volumes(paths):
    if set(paths) != ROLES:
        raise ValueError('Explicit execution, objects and database paths are required')
    records, free = {}, []
    for role, value in paths.items():
        path = Path(value)
        if not path.is_absolute() or not path.is_dir() or path.is_symlink():
            raise ValueError('Capacity paths must be existing absolute directories')
        resolved = path.resolve(strict=True)
        stat = resolved.stat()
        # Directory identity detects replaced/unmounted targets on the same device too.
        records[role] = {'path': str(resolved), 'device': stat.st_dev, 'inode': stat.st_ino}
        free.append(shutil.disk_usage(resolved).free)
    return records, min(free)  # Charge total growth against every volume, conservatively.


def sample(session, paths):
    policy = gate(session)
    records, free = inspect_volumes(paths)
    if policy.volumes and records != policy.volumes:
        raise ValueError('Capacity mount identity changed; drain and revalidate before reconfiguration')
    policy.volumes, policy.free_bytes, policy.sample_at = records, free, utcnow()
    # The gate serializes publication before measurement. Original bytes, orphan
    # files, snapshots and WAL remain reflected by the filesystem's free space.
    for row in session.scalars(select(CapacityReservation).where(CapacityReservation.state == 'published')):
        row.state = 'accounted'
    session.flush()
    return {'freeBytes': free, 'pendingBytes': pending_bytes(session), 'enabled': policy.enabled}
