"""Record the already installed Ubuntu sosreport update on hengxin-ai-245."""
import copy
import json
import os
from pathlib import Path
import socket

import codex_runtime_marker
import domestic_tasks_marker
import joint_studio_marker
import release
import scope_catalog
import scope_snapshot
import snapshot

ACCOUNT = 'hengxin-codex-accounts'
OLD = 'e030fa0a0e8082465a91b7d5be79fc4d70ec85e907f54906fa6bcdca0fe99d9c'
NEW = 'f07953638f0c5053a7ccc4a3411422fb270eab2ff6829fcc3c8a1156e62f0909'


def check_packages(raw):
    rows = json.loads(raw)
    if rows.count(['sos', '4.11.2']) != 1 or snapshot.sha(raw.encode()) != NEW:
        raise RuntimeError('Installed Python distribution list differs')
    rows[rows.index(['sos', '4.11.2'])][1] = '4.10.2'
    if snapshot.sha((json.dumps(sorted(rows)) + '\n').encode()) != OLD:
        raise RuntimeError('Previous Python distribution list differs')


def record(tool):
    u, store = tool.u, tool.store
    codex_runtime_marker.guard(u, store)
    domestic_tasks_marker.guard(u, store)
    joint_studio_marker.guard(u, store)
    split = store.root / 'intranet-split-migration.json'
    if split.exists():
        u.safe(split)
        if json.loads(split.read_bytes())['phase'] not in ('complete', 'rolled-back'):
            raise RuntimeError('Split migration pending')
    data = tool.load()
    if data['version'] != 2 or data['pending'] or data.get('migration_pending'):
        raise RuntimeError('Idle v2 ledger required')
    scope_catalog.check(data)
    if u.run(['dpkg-query', '-W', '-f=${Version}', 'sosreport']) != '4.11.2-0ubuntu0~24.04.2' or u.run(['dpkg', '-V', 'sosreport']):
        raise RuntimeError('Ubuntu package version or integrity differs')
    check_packages(u.native_run(u.contexts()[ACCOUNT], code=scope_snapshot.PACKAGES))
    updated = copy.deepcopy(data)
    state = updated['current']
    row = state['native'][ACCOUNT]
    if row['packages'] not in (OLD, NEW):
        raise RuntimeError('Unexpected ledger package digest')
    row['packages'] = NEW
    snapshot.same(state, tool.capture(data, runtime=True))
    if data['current'] == state:
        return
    updated['groups']['shared']['current'] = scope_snapshot.group(state, 'shared')
    scope_catalog.seal(updated)
    scope_catalog.check(updated)
    tool.save(updated)


if __name__ == '__main__':
    if socket.gethostname() != 'hengxin-ai-245' or os.geteuid() != 0:
        raise SystemExit('Only root on hengxin-ai-245 is supported')
    store = release.retention_store(Path('/var/lib/hengxin-release'))
    with store.locked():
        record(release.Release(store))
    print('SOSREPORT_LEDGER_OK')
