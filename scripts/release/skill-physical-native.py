"""Absent-aware exact native replacement while admission and both services are stopped."""
import json
from pathlib import Path

r = None


def install(work, data, source):
    native = r.helper('sku-native')
    files = r.helper('skill-reuse-native')
    native.stopped()
    r.helper('skill-reuse-gate').require_closed(work, data)
    r.helper('polling-database').backup_verified(work, data)
    if not (work/'NATIVE_PATCH_STARTED').exists():
        if not (work/'native-backup.json').exists():
            files.backup(work, data)
        files.records(work, data)
        r.private(work/'NATIVE_PATCH_STARTED', {'manifest': data['manifest']})
    for row in files.records(work, data):
        wanted = data['patch'][row['name']]['sha256']
        actual = files.fingerprint(Path(row['path']))
        r.require(actual in (row['sha256'], wanted), 'Native patch drift')
        if actual != wanted:
            files.atomic(row, (source/'api'/row['name']).read_bytes(), wanted)
    r.private(work/'NATIVE_INSTALLED', {'manifest': data['manifest']})
    r.helper('skill-physical-test').installed(work, data, source)
    r.helper('skill-reuse-preserve').verify(work, data)
    return 'NATIVE_PATCH_TESTED_SERVICES_REMAIN_STOPPED'


def restore(work, data):
    # Proven recovery preserves absent originals and prevents SIGKILL escalation.
    return r.helper('skill-reuse-native').restore(work, data)
