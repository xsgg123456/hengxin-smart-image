"""Single approved domestic Tasks maintenance, routed through release.py."""
from contextlib import contextmanager
import copy
from pathlib import Path

import catalog
import cleanup_history
import domestic_tasks_engine as migration
import domestic_tasks_marker as marker
import domestic_tasks_policy as policy
import engine
import joint_studio_fence as fence
import release
import scope_changes
import scope_engine
import scope_snapshot
import scopes
import snapshot


class Upgrade:
    def __init__(self, store, transition=policy):
        self.policy = transition
        self.tool, self.store, self.u = release.Release(store), store, engine.u

    def save(self, row, phase):
        row['phase'] = phase
        self.store.report(self.policy.MARKER, row)

    def read(self):
        row = marker.read(self.u, self.store, self.policy.MARKER)
        if not row:
            raise RuntimeError('No domestic Tasks maintenance transaction')
        return row

    def item(self, row):
        data = self.tool.load()
        item = data.get('pending') or row.get('item')
        if (not item or item.get('scope') != 'domestic' or item.get('mode') != 'full'
                or item.get('release') != row['release'] or item.get('rollback')):
            raise RuntimeError('Tasks transaction binding differs')
        if row.get('item') and item != row['item']:
            raise RuntimeError('Tasks pending state changed')
        self.tool.configure(item)
        return item

    @contextmanager
    def configured(self, item, descriptor):
        with scope_engine.context('domestic', 'full', backend=Path(item['target_backend']),
                                  frontend=Path(item['target_frontend']), domestic_publisher=True):
            with migration.context(item, descriptor, self.policy):
                yield

    def prepare(self, path):
        marker.guard(self.u, self.store)
        data = self.tool.load()
        current = data['current']
        if (data.get('version') != 2 or data.get('pending') or data.get('migration_pending')
                or current['schema']['domestic'] != self.policy.SOURCE
                or current['groups']['domestic']['backend_commit'] != self.policy.BASE
                or not scopes.has_domestic_publisher(current)):
            raise RuntimeError(f'Maintenance requires the idle reviewed {self.policy.SOURCE} domestic baseline')
        path = snapshot.release_path(path)
        if str(path) not in catalog.check(data)['staged']:
            raise RuntimeError('Tasks candidate must be staged through the release ledger')
        self.policy.validate(snapshot.manifest(self.u, current['groups']['domestic']['backend']),
                        snapshot.manifest(self.u, path))
        row = {'release': str(path), 'before_sha256': catalog.state_sha(current)}
        self.save(row, 'preparing')
        original = scope_changes.check
        def approved(*args, **kwargs):
            return self.policy.check(original, *args, **kwargs)
        with scopes.replace(scope_changes, check=approved):
            data = self.tool.prepare(path, 'full', 'domestic')
        row['item'] = copy.deepcopy(data['pending'])
        self.save(row, 'prepared')
        return row

    def deploy(self):
        row = self.read()
        if row['phase'] != 'prepared':
            raise RuntimeError(f'Maintenance is not prepared; use {self.policy.COMMAND}-recover')
        item = self.item(row)
        snapshot.same(item['before'], self.tool.capture(self.tool.load()))
        self.save(row, 'deploying')
        with fence.hold(self.u) as descriptor:
            with self.configured(item, descriptor):
                engine.apply()
        return self.finish()

    def verify_after(self, item, after):
        baseline = engine._read('prepared.json')
        configs = dict(item['before']['configs'])
        configs[str(self.u.COMPOSE)] = baseline['candidate']
        for name in scopes.NATIVE['domestic']:
            path = self.u.SYSTEMD / (name + '.service.d') / self.u.DROPIN
            configs[str(path)] = baseline['dropins'][name]
        snapshot.same(configs, after['configs'])
        expected = dict(item['before'], schema=dict(item['before']['schema'], domestic=self.policy.TARGET))
        snapshot.unchanged_runtime(expected, after)
        for side in ('overseas', 'shared'):
            snapshot.same(scope_snapshot.group(item['before'], side), scope_snapshot.group(after, side))
            snapshot.same(item['before']['asset_fallbacks'][side], after['asset_fallbacks'][side])
        actual = after['groups']['domestic']
        if actual['frontend'] != item['release'] or actual['backend'] != item['target_backend']:
            raise RuntimeError('Tasks candidate source is not running')
        scope_snapshot.unchanged_other(item['census'], scope_snapshot.census(
            self.u, domestic_publisher=True), 'domestic')

    def finish(self):
        row = self.read()
        # A terminal receipt can outlive its source and later successful deploys.
        # Replaying it must never close the current domestic ingress.
        if row['phase'] == 'complete':
            return row
        if row['phase'] not in ('deploying', 'forward-required', 'ledger-writing'):
            raise RuntimeError('Tasks transaction cannot finish in this phase')
        item = self.item(row)
        try:
            completed = self.finish_locked(row, item)
        except BaseException:
            # Candidate entries are already open after engine.apply. A failed
            # verification/ledger write must not continue accepting new jobs.
            with scope_engine.context('domestic', 'full', domestic_publisher=True):
                self.u.app_command('stop', self.u.ENTRIES)
            raise
        self.tool.cleanup(completed, automatic=True)
        return row

    def finish_locked(self, row, item):
        with fence.hold(self.u) as descriptor:
            with self.configured(item, descriptor):
                migration.check_migration(self.u, item['before'], descriptor, self.policy)
                if not (self.u.WORK / 'applied.json').exists():
                    raise RuntimeError('Tasks candidate switch is incomplete')
                engine.apply()  # Verify applied config and candidate digest again.
                stopped = tuple(name for name, info in self.u.containers().items()
                                if name in self.u.ENTRIES and not info['State']['Running'])
                if stopped:
                    self.u.app_command('up', stopped)
                    migration.check_restarts(self.u)
            data = self.tool.load()
            after = self.tool.capture(data, runtime=True)
            self.verify_after(item, after)
            if data.get('pending'):
                history = set(data.get('source_history', []))
                history.update(cleanup_history.sources(data['current']) | cleanup_history.sources(after))
                completed = dict(data, current=after, previous=item['before'], pending=None,
                                 last=item.copy(), source_history=sorted(history))
                catalog.advance(self.u, self.store, data, completed, item)
                row['item'] = copy.deepcopy(item)
                row['after_sha256'] = catalog.state_sha(after)
                self.save(row, 'ledger-writing')
                self.tool.save(completed)
            else:
                if catalog.state_sha(after) != row.get('after_sha256'):
                    raise RuntimeError('Tasks success ledger cannot be reconciled')
                snapshot.same(data['current'], after)
                catalog.check(data)
                completed = data
            self.save(row, 'complete')
        return completed

    def recover(self):
        row = self.read()
        if row['phase'] in marker.TERMINAL:
            return row
        data = self.tool.load()
        if not data.get('pending'):
            if row['phase'] == 'ledger-writing':
                return self.finish()
            if row['phase'] == 'restoring-ledger':
                if (snapshot.schemas(self.u) != row['item']['before']['schema']
                        or data['current'] != row['item']['before']):
                    raise RuntimeError('Tasks recovery ledger differs')
                snapshot.same(data['current'], self.tool.capture(data, runtime=True))
                self.save(row, row['restored_phase'])
                return row
            if row['phase'] == 'preparing' and not row.get('item'):
                if catalog.state_sha(data['current']) != row['before_sha256']:
                    raise RuntimeError('Tasks baseline drift during preparation')
                snapshot.same(data['current'], self.tool.capture(data, runtime=True))
                self.save(row, 'cancelled')
                return row
            raise RuntimeError('Tasks pending ledger disappeared')
        pending = data['pending']
        if row['phase'] == 'preparing' and not Path(pending['work']).exists():
            if (pending.get('scope') != 'domestic' or pending.get('release') != row['release']
                    or catalog.state_sha(data['current']) != row['before_sha256']):
                raise RuntimeError('Tasks preparation binding drift')
            snapshot.same(data['current'], self.tool.capture(data, runtime=True))
            data['pending'] = None
            self.tool.save(data)
            self.save(row, 'cancelled')
            return row
        item = self.item(row)
        with fence.hold(self.u) as descriptor:
            with self.configured(item, descriptor):
                if (self.u.WORK / self.policy.RECEIPT).exists():
                    state = engine._load_state(engine._read('prepared.json'))
                    fence.wait_database(self.u, state['ctx']['hengxin-vps-codex-worker'])
                schema = snapshot.schemas(self.u)
                if schema == item['before']['schema']:
                    started = (self.u.WORK / 'started.json').exists()
                    if started:
                        engine.recover()
                elif schema == dict(item['before']['schema'], domestic=self.policy.TARGET):
                    migration.resume(item, descriptor, self.policy)
                    self.save(row, 'forward-required')
                    started = None
                else:
                    raise RuntimeError('Unknown schema drift; automatic recovery refused')
            if started is not None:
                snapshot.same(item['before'], self.tool.capture(data, runtime=True))
                data['pending'] = None
                catalog.finished_attempt(self.u, self.store, data, item)
                row.update(item=copy.deepcopy(item), restored_phase='rolled-back' if started else 'cancelled')
                self.save(row, 'restoring-ledger')
                self.tool.save(data)
                self.save(row, row['restored_phase'])
                return row
        return self.finish()


def run(store, args, transition=policy):
    if args.scope != 'domestic' or args.mode != 'full':
        raise RuntimeError('Tasks maintenance requires --scope domestic --mode full')
    marker.guard(engine.u, store, except_name=transition.MARKER)
    tool = Upgrade(store, transition)
    action = args.action.removeprefix(transition.COMMAND + '-')
    if action == 'prepare':
        if args.release is None:
            raise RuntimeError(f'{transition.COMMAND}-prepare requires --release')
        row = tool.prepare(args.release)
    else:
        row = tool.read() if action == 'status' else getattr(tool, action)()
    return {'phase': row['phase'], 'work': (row.get('item') or {}).get('work')}
