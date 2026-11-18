"""Audited domestic Studio gateway change, executed under the standard LAN release lock."""
import copy
import json
from pathlib import Path
import tempfile

import catalog
from domestic_upload_probe import verify_probes
import domestic_upload_routes
import scope_catalog
import scope_snapshot
import scopes
import snapshot
import split_config


BASELINE_SHA = 'b9ab10485f7e23d62790b6821c515ee0142dd0173ce29cdaafc49b429d872d2b'
KIND = 'domestic-upload-gateway'
RECEIPT = 'domestic_upload_gateway'
TARGET = '/etc/nginx/conf.d/default.conf'
CONTAINER = 'hengxin-lan-domestic-web'


def binding(tool):
    u = tool.u
    path = u.ROOT / 'nginx.conf'
    u.safe(path)
    info = json.loads(u.run(['docker', 'inspect', CONTAINER]))[0]
    mounts = [item for item in info['Mounts'] if item['Destination'] == TARGET]
    if (len(mounts) != 1 or mounts[0]['Type'] != 'bind' or mounts[0]['RW']
            or mounts[0]['Source'] != str(path)):
        raise RuntimeError('Unexpected running gateway configuration mount')
    stat = path.stat()
    mounted = u.run(['docker', 'exec', CONTAINER, 'stat', '-Lc', '%d:%i', TARGET]).strip()
    if mounted != f'{stat.st_dev}:{stat.st_ino}':
        raise RuntimeError('Gateway no longer sees the host configuration inode')
    return [stat.st_dev, stat.st_ino]


def census(tool, data):
    return scope_snapshot.census(tool.u, domestic_publisher=scopes.has_domestic_publisher(data['current']))


def check_candidate(tool, content):
    tool.u.safe(tool.u.COMPOSE)
    with tempfile.TemporaryDirectory(dir=tool.store.root) as scratch:
        path = Path(scratch) / 'nginx.conf'
        tool.u.write(path, content, mode=0o600, exclusive=True)
        split_config.check_gateway(tool.u, path, json.loads(tool.u.COMPOSE.read_bytes()))


def configs(original):
    if snapshot.sha(original) != BASELINE_SHA:
        raise RuntimeError('Domestic upload maintenance requires the reviewed gateway baseline')
    candidate = domestic_upload_routes.render(original)
    if candidate == original:
        raise RuntimeError('Domestic upload candidate is identical to baseline')
    return original, candidate


def verify(tool, data, content, enabled, identities, inode):
    expected = copy.deepcopy(data['current'])
    expected['configs'][str(tool.u.ROOT / 'nginx.conf')] = snapshot.sha(content)
    snapshot.same(expected, tool.capture(data, runtime=True))
    probes = verify_probes(enabled)
    if census(tool, data) != identities or binding(tool) != inode:
        raise RuntimeError('Gateway maintenance changed a service identity or bind mount')
    return expected, probes


def is_partial(actual, source, target):
    # The file bind requires in-place writes. Only accept an interrupted prefix
    # of the known target followed by the corresponding original suffix.
    count = 0
    for left, right in zip(actual, target):
        if left != right:
            break
        count += 1
    return actual == target or actual == target[:count] + source[count:]


def recover(tool):
    data = tool.load()
    item = data['pending']
    if not item or item.get('kind') != KIND:
        raise RuntimeError('No domestic upload gateway transaction to recover')
    if (item.get('phase') not in ('switching', 'restoring') or item.get('action') not in ('apply', 'rollback')
            or catalog.state_sha(dict(data, pending=None)) != item['ledger_sha256']):
        raise RuntimeError('Gateway transaction or original ledger drift')
    original, candidate = configs(item['original'].encode())
    prior_enabled = item['action'] == 'rollback'
    source, target = (candidate, original) if prior_enabled else (original, candidate)
    path = tool.u.ROOT / 'nginx.conf'
    if (data['current']['configs'][str(path)] != snapshot.sha(source)
            or binding(tool) != item['inode']):
        raise RuntimeError('Gateway recovery baseline or bind identity changed')
    actual = path.read_bytes()
    if item['phase'] == 'restoring':
        started = item['recovery_input'].encode()
        if not is_partial(started, source, target) or not is_partial(actual, started, source):
            raise RuntimeError('Unrelated gateway drift during recovery')
    else:
        if not is_partial(actual, source, target):
            raise RuntimeError('Unrelated gateway drift prevents recovery')
        item.update(phase='restoring', recovery_input=actual.decode())
        tool.save(data)
    if actual != source:
        split_config.bound_write(tool.u, path, source, snapshot.sha(actual))
    split_config.reload_gateway(tool.u)
    _, probes = verify(tool, data, source, prior_enabled, item['census'], item['inode'])
    tool.save(dict(data, pending=None))
    return {'action': 'recover', 'enabled': prior_enabled, 'probes': probes}


def run(tool, action):
    if action == 'recover':
        return recover(tool)
    if action not in ('apply', 'rollback'):
        raise ValueError('Unknown gateway maintenance action')
    data = tool.load()
    if data.get('version') != 2 or data.get('pending') or data.get('migration_pending'):
        raise RuntimeError('Domestic upload gateway maintenance requires an idle scoped ledger')
    catalog.before(tool.u, tool.store, data)
    receipt = data.get(RECEIPT)
    if action == 'rollback' and not receipt:
        raise RuntimeError('No domestic upload gateway change to roll back')
    path = tool.u.ROOT / 'nginx.conf'
    inode = binding(tool)
    original, candidate = configs(receipt['original'].encode() if receipt else path.read_bytes())
    enabled = receipt['enabled'] if receipt else False
    source = candidate if enabled else original
    if (path.read_bytes() != source or data['current']['configs'].get(str(path)) != snapshot.sha(source)):
        raise RuntimeError('Live gateway and recorded upload configuration differ')
    identities = census(tool, data)
    _, before_probes = verify(tool, data, source, enabled, identities, inode)
    requested = action == 'apply'
    if enabled == requested:
        return {'action': action, 'enabled': enabled, 'changed': False, 'probes': before_probes}
    target = candidate if requested else original
    check_candidate(tool, target)
    if tool.load() != data or binding(tool) != inode:
        raise RuntimeError('Gateway or release ledger changed during preparation')
    item = {'kind': KIND, 'phase': 'switching', 'action': action, 'original': original.decode(),
            'inode': inode, 'census': identities, 'ledger_sha256': catalog.state_sha(data)}
    tool.save(dict(data, pending=item))
    try:
        split_config.bound_write(tool.u, path, target, snapshot.sha(source))
        split_config.reload_gateway(tool.u)
        after, probes = verify(tool, data, target, requested, identities, inode)
        completed = copy.deepcopy(data)
        completed['current'] = after
        completed[RECEIPT] = {'enabled': requested, 'original': original.decode(), 'sha256': snapshot.sha(target),
                              'before_probes': before_probes, 'probes': probes}
        scope_catalog.seal(completed)
        scope_catalog.check(completed)
        tool.save(completed)
    except BaseException:
        # Saving is atomic. A late fsync error must not undo an already committed switch.
        if (tool.load().get('pending') or {}).get('kind') == KIND:
            recover(tool)
        raise
    return {'action': action, 'enabled': requested, 'changed': True, 'sha256': snapshot.sha(target),
            'before_probes': before_probes, 'probes': probes}
