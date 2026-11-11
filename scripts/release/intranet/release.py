"""Intranet-only release entry. No public host option, no runtime upgrades."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import socket
import time

import engine
import operations
import snapshot


def retention_store(root):
    spec = importlib.util.spec_from_file_location('lan_retention_state',
        Path(__file__).resolve().parent.parent / 'release-retention-state.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Store(root)


class Release:
    def __init__(self, store):
        self.store = store
        self.u = engine.u
        self.path = store.root / 'intranet.json'

    def load(self):
        if not self.path.exists():
            raise RuntimeError('Initialize verified live baseline first: init')
        self.u.safe(self.path)
        data = json.loads(self.path.read_bytes())
        if data.get('version') != 1 or not isinstance(data.get('current'), dict):
            raise RuntimeError('Invalid LAN release ledger')
        return data

    def save(self, data):
        self.store.report('intranet.json', data)

    def init(self):
        if self.path.exists():
            data = self.load()
            snapshot.same(data['current'], snapshot.capture(self.u, runtime=True))
            return data
        data = {'version': 1, 'current': snapshot.capture(self.u, runtime=True),
                'previous': None, 'pending': None, 'last': None}
        self.save(data)
        return data

    def prepare(self, release, mode):
        data = self.load()
        if data['pending']:
            raise RuntimeError('Pending release exists; recover or cancel it first')
        before = snapshot.capture(self.u)
        snapshot.same(data['current'], before)
        release = snapshot.release_path(release)
        if str(release) in (before['backend'], before['frontend']):
            raise RuntimeError('Candidate must be a new immutable directory')
        old = snapshot.manifest(self.u, before['backend'])
        candidate = snapshot.manifest(self.u, release)
        snapshot.compatible(old, candidate, mode)
        operations.keep_assets(self.u, Path(before['frontend']), release)
        parent = self.store.root / 'intranet-transactions'
        parent.mkdir(mode=0o700, exist_ok=True)
        self.u.safe(parent)
        work = parent / (release.name + '-' + str(time.time_ns()))
        pending = {'release': str(release), 'work': str(work), 'mode': mode,
                   'phase': 'preparing', 'before': before}
        data['pending'] = pending
        self.save(data)
        engine.configure(release, work)
        (operations.prepare_web(self.u) if mode == 'frontend' else engine.prepare())
        pending['phase'] = 'prepared'
        self.save(data)
        return data

    def configure(self, item):
        release = snapshot.release_path(item['release'])
        work = Path(item['work'])
        if work.parent != self.store.root / 'intranet-transactions':
            raise RuntimeError('Transaction outside LAN ledger')
        self.u.safe(work)
        engine.configure(release, work)

    def restore(self, item):
        self.configure(item)
        if snapshot.schemas(self.u) != item['before']['schema'] or self.u.data_identity() != item['before']['data']:
            raise RuntimeError('Schema/data drift: automatic code recovery refused')
        if not (self.u.WORK / 'started.json').exists():
            snapshot.same(item['before'], snapshot.capture(self.u, runtime=True))
            return
        if item['mode'] == 'frontend':
            operations.recover_web(self.u)
        else:
            engine.recover()
        snapshot.same(item['before'], snapshot.capture(self.u, runtime=True))

    def deploy(self):
        data = self.load()
        item = data['pending']
        if not item or item['phase'] != 'prepared':
            raise RuntimeError('No prepared release; interrupted releases require recover')
        self.configure(item)
        snapshot.same(item['before'], snapshot.capture(self.u))
        if item['mode'] != 'frontend':
            operations.backup(self.u, self.u.WORK)
        item['phase'] = 'deploying'
        self.save(data)
        try:
            (operations.apply_web(self.u) if item['mode'] == 'frontend' else engine.apply())
            after = snapshot.capture(self.u, runtime=True)
            snapshot.unchanged_runtime(item['before'], after)
            if after['frontend'] != item['release'] or (item['mode'] != 'frontend' and after['backend'] != item['release']):
                raise RuntimeError('Running source did not switch to candidate')
            completed = dict(data, current=after, previous=item['before'], last=item.copy(), pending=None)
            self.save(completed)
        except BaseException:
            # Keep pending until restored state is independently verified. No DB rewind.
            self.restore(item)
            data['pending']['phase'] = 'recovered'
            self.save(data)
            raise
        return completed

    def recover(self):
        data = self.load()
        item = data['pending']
        if not item:
            snapshot.same(data['current'], snapshot.capture(self.u))
            return data
        if item['phase'] in ('preparing', 'prepared') and not (Path(item['work']) / 'started.json').exists():
            raise RuntimeError('Unstarted release: use cancel after verifying live baseline')
        self.restore(item)
        data.update(current=item['before'], pending=None)
        if item['phase'] == 'rollback':
            data.update(previous=None, last=None)
        self.save(data)
        return data

    def rollback(self):
        data = self.load()
        if data['pending'] or not data['previous'] or not data['last']:
            raise RuntimeError('No previous successful release or a transaction is pending')
        snapshot.same(data['current'], snapshot.capture(self.u))
        item = dict(data['last'], phase='rollback')
        data['pending'] = item
        self.save(data)
        return self.recover()

    def cancel(self):
        data = self.load()
        item = data['pending']
        if not item:
            return data
        if (Path(item['work']) / 'started.json').exists() or item['phase'] not in ('preparing', 'prepared'):
            raise RuntimeError('Started transaction cannot be abandoned; use recover')
        snapshot.same(data['current'], snapshot.capture(self.u))
        data['pending'] = None
        self.save(data)
        return data


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('init', 'status', 'verify', 'prepare', 'deploy', 'recover', 'rollback', 'cancel'))
    parser.add_argument('--release', type=Path)
    parser.add_argument('--mode', choices=('full', 'frontend'), default='full')
    args = parser.parse_args(argv)
    if socket.gethostname() != 'hengxin-ai-245' or os.geteuid() != 0:
        raise RuntimeError('Only root on hengxin-ai-245 is supported')
    engine.u.safe(engine.u.ROOT)
    store = retention_store(Path('/var/lib/hengxin-release'))
    engine.u.safe(store.root)
    with store.locked():
        tool = Release(store)
        if args.action == 'prepare':
            if args.release is None:
                parser.error('prepare requires --release')
            data = tool.prepare(args.release, args.mode)
        elif args.action in ('status', 'verify'):
            data = tool.load()
            if args.action == 'verify':
                snapshot.same(data['current'], snapshot.capture(engine.u, runtime=True))
        else:
            if args.release is not None:
                parser.error('--release is only valid for prepare')
            data = getattr(tool, args.action)()
        print(json.dumps({'action': args.action, 'backend_commit': data['current']['backend_commit'],
              'frontend_commit': data['current']['frontend_commit'], 'previous': bool(data['previous']),
              'pending': data['pending']['phase'] if data['pending'] else None}, indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        raise SystemExit('LAN_RELEASE_REFUSED: ' + (str(exc) if isinstance(exc, RuntimeError)
                                                 else type(exc).__name__)) from None
