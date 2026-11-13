"""Intranet-only release entry. No public host option, no runtime upgrades."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import socket
import time

import engine
import full_cleanup as cleanup
import catalog
import cleanup_history
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
        if data.get('version') not in (1, 2) or not isinstance(data.get('current'), dict):
            raise RuntimeError('Invalid LAN release ledger')
        return data

    def capture(self, data, runtime=False):
        return snapshot.capture_for(self.u, data, runtime=runtime)

    def phase(self, action, item):
        if item.get('scope'):
            import scope_release
            return scope_release.phase(action, item)
        if item['mode'] == 'frontend':
            return getattr(operations, {'prepare': 'prepare_web', 'apply': 'apply_web', 'recover': 'recover_web'}[action])(self.u)
        return getattr(engine, action)()

    def save(self, data):
        self.store.report('intranet.json', data)

    def init(self):
        if self.path.exists():
            data = self.load()
            snapshot.same(data['current'], self.capture(data, runtime=True))
            return data
        data = {'version': 1, 'current': snapshot.capture(self.u, runtime=True),
                'previous': None, 'pending': None, 'last': None}
        self.save(data)
        return data

    def prepare(self, release, mode, scope=None, rollback_target=None, fast_maintenance=False):
        if fast_maintenance and (scope not in ('domestic', 'overseas') or mode != 'full' or rollback_target):
            raise RuntimeError('Fast maintenance requires a full business release')
        data = self.load()
        if data['pending']:
            raise RuntimeError('Pending release exists; recover or cancel it first')
        if data.get('migration_pending'):
            raise RuntimeError('Complete migration verification before publishing')
        before = self.capture(data)
        snapshot.same(data['current'], before)
        data = catalog.before(self.u, self.store, data)
        release = snapshot.release_path(release)
        import scope_release
        selected = scope_release.selection(data, before, scope)
        if not rollback_target and str(release) in (selected['backend'], selected['frontend']):
            raise RuntimeError('Candidate must be a new immutable directory')
        old = snapshot.manifest(self.u, selected['backend'])
        candidate = snapshot.manifest(self.u, release)
        if scope:
            scope_release.candidate(self.u, data, before, release, mode, scope, bool(rollback_target),
                                    fast_maintenance=fast_maintenance)
        else:
            snapshot.compatible(old, candidate, mode)
        if not rollback_target:
            operations.keep_assets(self.u, Path(selected['frontend']), release)
        parent = self.store.root / 'intranet-transactions'
        parent.mkdir(mode=0o700, exist_ok=True)
        self.u.safe(parent)
        work = parent / (release.name + '-' + str(time.time_ns()))
        pending = {'release': str(release), 'work': str(work), 'mode': mode,
                   'phase': 'preparing', 'before': before}
        if fast_maintenance:
            pending['maintenance'] = 'codex-fast-20261113'
        if scope:
            import scope_snapshot
            import scopes
            pending.update(scope=scope, target_frontend=str(release),
                           target_backend=rollback_target['backend'] if rollback_target else
                           selected['backend'] if mode == 'frontend' else str(release),
                           census=scope_snapshot.census(self.u, domestic_publisher=scopes.has_domestic_publisher(before)),
                           rollback=bool(rollback_target))
        data['pending'] = pending
        self.save(data)
        engine.configure(release, work)
        self.phase('prepare', pending)
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
            snapshot.same(item['before'], self.capture(self.load(), runtime=True))
            return
        self.phase('recover', item)
        snapshot.same(item['before'], self.capture(self.load(), runtime=True))

    def deploy(self):
        data = self.load()
        item = data['pending']
        if not item or item['phase'] != 'prepared':
            raise RuntimeError('No prepared release; interrupted releases require recover')
        self.configure(item)
        snapshot.same(item['before'], self.capture(data))
        if item['mode'] != 'frontend':
            if item.get('scope'):
                operations.backup(self.u, self.u.WORK, scope=item['scope'])
            else:
                operations.backup(self.u, self.u.WORK)
        item['phase'] = 'deploying'
        self.save(data)
        try:
            self.phase('apply', item)
            after = self.capture(data, runtime=True)
            snapshot.unchanged_runtime(item['before'], after)
            if item.get('scope'):
                import scope_release, scope_snapshot, scopes
                actual = scope_snapshot.group(after, item['scope'])
                scope_release.unaffected(item['census'], scope_snapshot.census(
                    self.u, domestic_publisher=scopes.has_domestic_publisher(after)), item['scope'], item['mode'])
            else:
                actual = after
            if actual['frontend'] != item['release'] or (item['mode'] != 'frontend' and actual['backend'] != item.get('target_backend', item['release'])):
                raise RuntimeError('Running source did not switch to candidate')
            history = set(data.get('source_history', []))
            history.update(cleanup_history.sources(data['current']) | cleanup_history.sources(data['previous']))
            history.update(cleanup_history.sources(after))
            completed = dict(data, current=after, previous=item['before'], last=item.copy(),
                             pending=None, source_history=sorted(history))
            catalog.advance(self.u, self.store, data, completed, item)
            self.save(completed)
        except BaseException:
            # Keep pending until restored state is independently verified. No DB rewind.
            self.restore(item)
            data['pending']['phase'] = 'recovered'
            self.save(data)
            raise
        # Cleanup is outside the deployment recovery block: never undo a successful
        # release because disk housekeeping failed after the new ledger was saved.
        self.cleanup(completed, automatic=True)
        return completed

    def cleanup(self, data=None, apply=True, automatic=False):
        data = data or self.load()
        try:
            report = cleanup.execute(self.u, self.store, data, apply=apply)
        except Exception as exc:
            if not automatic:
                raise
            report = {'status': 'warning', 'error': type(exc).__name__, 'deleted': []}
            try:
                self.store.report('intranet-cleanup-warning.json', report)
            except Exception:
                pass  # Console warning survives even if the disk is full.
        print('LAN_CLEANUP ' + json.dumps(report), flush=True)
        return report

    def recover(self):
        data = self.load()
        item = data['pending']
        if not item:
            snapshot.same(data['current'], self.capture(data))
            return data
        if item['phase'] in ('preparing', 'prepared') and not (Path(item['work']) / 'started.json').exists():
            raise RuntimeError('Unstarted release: use cancel after verifying live baseline')
        self.restore(item)
        data.update(current=item['before'], pending=None)
        if item['phase'] == 'rollback':
            data.update(previous=None, last=None)
        catalog.recover(data)
        catalog.finished_attempt(self.u, self.store, data, item)
        self.save(data)
        return data

    def rollback(self, scope=None):
        data = self.load()
        if data.get('version') == 2:
            import scope_release
            return scope_release.rollback(self, scope)
        if data['pending'] or not data['previous'] or not data['last']:
            raise RuntimeError('No previous successful release or a transaction is pending')
        snapshot.same(data['current'], self.capture(data))
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
        snapshot.same(data['current'], self.capture(data))
        data['pending'] = None
        catalog.finished_attempt(self.u, self.store, data, item)
        self.save(data)
        return data


def main(argv=None):
    import sys
    from release_cli import run
    return run(sys.modules[__name__], argv)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        raise SystemExit('LAN_RELEASE_REFUSED: ' + (str(exc) if isinstance(exc, RuntimeError)
                                                 else type(exc).__name__)) from None
