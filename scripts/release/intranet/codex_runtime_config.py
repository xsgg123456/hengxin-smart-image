"""Pinned configuration, installed binary and release ledger checks for the Codex switch."""
import base64
import copy
import hashlib
import json
from pathlib import Path
import re
import stat
import types

import domestic_tasks_marker
import engine
import joint_studio_marker
import joint_studio_paths as gates
import scope_catalog
import scope_snapshot
import snapshot

u = engine.u
OLD, NEW = '0.167.1', '0.169.1'
DIGEST = {OLD: 'dd5bfdf19d794dcc6fb482d2d5a2d9fb31d11f6caa44b303bb72890d461e8a02',
          NEW: '105102da93472e8641b839554c7713849817943a09f76db3f4ea333fd67ce8b5'}
HELPER = Path('/opt/hengxin-runtime/codex-upgrade-20261111/upgrade_codex.py')
HELPER_SHA = 'd6e34d3911ba8772021ea7254557bb90f7efb62376df2eca84e76f8ecd6e5b01'
WORKERS = ('hengxin-vps-codex-worker', 'hengxin-overseas-worker')
AUX = ('hengxin-retention', 'hengxin-domestic-deletions', 'hengxin-overseas-outbox')
ACCOUNT = 'hengxin-codex-accounts'
SERVICES = (*WORKERS, *AUX, ACCOUNT)
ENV_DIR = Path('/etc/hengxin-lan')
ENVS = {ENV_DIR / (n + '.env'): n for n in (*WORKERS, *AUX)}
UNIT = Path('/etc/systemd/system') / (ACCOUNT + '.service')
TEMPLATE = ENV_DIR / UNIT.name
INVENTORY = Path('/opt/hengxin-lan/native-env.json')
FILES = (*ENVS, UNIT, TEMPLATE, INVENTORY)


def binary(version):
    return '/opt/hengxin-runtime/codex-' + version + '/bin/codex'


def key(service):
    return 'OVERSEAS_CODEX_' if 'overseas' in service else 'CODEX_'


def substitute(path, data, source, target):
    count = len(ENVS) if path == INVENTORY else 1
    versions = count if path in (UNIT, TEMPLATE) else count * 2
    old, new = source.encode(), target.encode()
    if (data.count(binary(source).encode()) != count or data.count(old) != versions
            or new in data):
        raise RuntimeError('Codex configuration reference drift: ' + str(path))
    if path in ENVS:
        for suffix, value in [('BINARY', binary(source)), ('VERSION', source)]:
            name = (key(ENVS[path]) + suffix).encode()
            if not re.search(rb'(?m)^' + name + rb'=("?)' + re.escape(value.encode()) + rb'\1$', data):
                raise RuntimeError('Unexpected environment setting: ' + str(path))
    elif path == INVENTORY:
        tree = json.loads(data)
        for service in ENVS.values():
            prefix = key(service)
            if (tree[service].get(prefix+'BINARY'), tree[service].get(prefix+'VERSION')) != (binary(source), source):
                raise RuntimeError('Unexpected persistent runtime inventory')
    elif path not in (UNIT, TEMPLATE) or not re.search(
            rb'"?--binary"?\s+"?' + re.escape(binary(source).encode()) + rb'"?(?=\s|$)', data):
        raise RuntimeError('Account binary argument differs')
    return data.replace(old, new)


def expected_state(before, records, source, target):
    result = copy.deepcopy(before)
    for path in FILES:
        previous, updated = records[str(path)]['before'], records[str(path)]['after']
        if str(path) not in result['configs'] and path in (TEMPLATE, INVENTORY):
            continue  # Deployment templates are independently verified from disk.
        if result['configs'].get(str(path)) != previous:
            raise RuntimeError('Ledger configuration drift: ' + str(path))
        result['configs'][str(path)] = updated
    if set(result['binaries']) != set(WORKERS):
        raise RuntimeError('Unexpected worker binary inventory')
    for values in result['binaries'].values():
        if values.pop(binary(source), None) != DIGEST[source] or binary(target) in values:
            raise RuntimeError('Ledger worker binary differs')
        values[binary(target)] = DIGEST[target]
    return result


def reseal(data, expected):
    result = copy.deepcopy(data)
    result['current'] = expected
    for scope in ('domestic', 'overseas'):
        result['groups'][scope]['current'] = scope_snapshot.group(expected, scope)
    scope_catalog.seal(result)
    scope_catalog.check(result)
    return result


def prerequisites(store):
    path = store.root / 'intranet-split-migration.json'
    if path.exists():
        u.safe(path)
        if json.loads(path.read_bytes())['phase'] not in ('complete', 'rolled-back'):
            raise RuntimeError('Split migration pending')
    domestic_tasks_marker.guard(u, store)
    joint_studio_marker.guard(u, store)
    u.safe(HELPER)
    content = HELPER.read_bytes()
    if snapshot.sha(content) != HELPER_SHA:
        raise RuntimeError('Reviewed account drain helper differs')
    helper = types.ModuleType('pinned_account_drain')
    exec(compile(content, str(HELPER), 'exec'), helper.__dict__)
    for version, expected in DIGEST.items():
        path = Path(binary(version))
        u.safe(path)
        with path.open('rb') as stream:
            actual = hashlib.file_digest(stream, 'sha256').hexdigest()
        if actual != expected or u.run([str(path), '--version']).strip() != 'codex-cli ' + version:
            raise RuntimeError('Installed Codex differs: ' + version)
    return helper


def read_files(source, target):
    records = {}
    for path in FILES:
        u.safe(path)
        info, content = path.stat(), path.read_bytes()
        if not stat.S_ISREG(info.st_mode) or info.st_gid != 0:
            raise RuntimeError('Unexpected config type/group: ' + str(path))
        candidate = substitute(path, content, source, target)
        records[str(path)] = dict(original=base64.b64encode(content).decode(), mode=stat.S_IMODE(info.st_mode),
                                  before=snapshot.sha(content), after=snapshot.sha(candidate))
    return records


def configs(state, action):
    for path in FILES:
        u.safe(path)
        row = state['files'][str(path)]
        original = base64.b64decode(row['original'], validate=True)
        updated = substitute(path, original, state['source'], state['target'])
        actual = path.read_bytes()
        if (snapshot.sha(original) != row['before'] or snapshot.sha(updated) != row['after']
                or stat.S_IMODE(path.stat().st_mode) != row['mode'] or path.stat().st_gid != 0):
            raise RuntimeError('Configuration metadata differs: ' + str(path))
        if action == 'apply' and actual == original:
            u.write(path, updated, row['mode'])
            gates.sync_directory(path.parent)
        elif action == 'restore' and actual == updated:
            u.write(path, original, row['mode'])
            gates.sync_directory(path.parent)
        elif actual != (updated if action == 'after' else original) or action == 'apply':
            raise RuntimeError('Concurrent configuration drift: ' + str(path))
