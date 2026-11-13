"""One-time LAN joint upgrade, bound to the existing release lock and ledger."""
import argparse
import json
from pathlib import Path
import socket
import os
import time

import catalog
import engine
import joint_studio_engine as joint_engine
import joint_studio_forward as forward
import joint_studio_fence as fence
import joint_studio_marker as marker
import joint_studio_packages as packages
import joint_studio_paths as paths
import joint_studio_state as joint_state
import operations
import release
import scope_snapshot
import scopes
import snapshot


class Upgrade:
    def __init__(self, store):
        self.store, self.u = store, engine.u
        self.tool = release.Release(store)

    def save(self, row, phase):
        row['phase'] = phase
        self.store.report(marker.NAME, row)

    def read(self):
        row = marker.read(self.u, self.store)
        if not row:
            raise RuntimeError('No domestic Studio migration record')
        work = Path(row['work'])
        if work.parent != self.store.root / 'intranet-transactions':
            raise RuntimeError('Joint transaction is outside the ledger')
        self.u.safe(work)
        return row

    def before(self, row):
        path = Path(row['work']) / 'ledger.before.json'
        self.u.safe(path)
        raw = path.read_bytes()
        if self.u.digest(raw) != row['ledger_before_sha256']:
            raise RuntimeError('Joint baseline ledger changed')
        return json.loads(raw)

    @staticmethod
    def flagged(data):
        return dict(data, migration_pending=True)

    def configure(self, row, external_fence=None, private_gateway=True):
        backend = snapshot.release_path(row['backend'])
        fronts = {name: snapshot.release_path(path) for name, path in row['frontends'].items()}
        if set(fronts) != set(scopes.GROUPS):
            raise RuntimeError('Joint frontend scope changed')
        engine.configure(backend, Path(row['work']))
        return joint_engine.context(backend, fronts, row['schema'], external_fence=external_fence,
                                    private_gateway=private_gateway)

    def prepare(self, frontends):
        existing = marker.read(self.u, self.store)
        if existing and existing['phase'] not in ('rolled-back', 'cancelled'):
            raise RuntimeError('Existing Studio migration record requires review')
        if existing:
            prior = self.read()
            archive = Path(prior['work']) / 'studio-marker.final.json'
            raw = json.dumps(prior, sort_keys=True).encode()
            if archive.exists():
                self.u.safe(archive)
                if archive.read_bytes() != raw:
                    raise RuntimeError('Prior Studio migration record differs')
            else:
                self.u.write(archive, raw, exclusive=True)
        data = self.tool.load()
        if data.get('version') != 2 or data.get('pending') or data.get('migration_pending'):
            raise RuntimeError('Joint upgrade requires an idle scoped ledger')
        before = self.tool.capture(data, runtime=True)
        snapshot.same(data['current'], before)
        data = catalog.before(self.u, self.store, data)
        if before['schema'].get('domestic') != '0032' or scopes.has_domestic_publisher(before):
            raise RuntimeError('Unexpected pre-upgrade domestic runtime')
        roots = {name: snapshot.release_path(value) for name, value in frontends.items()}
        packages.verify(self.u, before, roots)
        if any(str(root) not in data['retention']['staged'] for root in roots.values()):
            raise RuntimeError('All three packages must be staged through the release ledger')
        paths.identities(self.u.contexts())
        for name, root in roots.items():
            operations.keep_assets(self.u, Path(before['groups'][name]['frontend']), root)
        packages.verify(self.u, before, roots)
        parent = self.store.root / 'intranet-transactions'
        parent.mkdir(mode=0o700, exist_ok=True)
        self.u.safe(parent)
        work = parent / ('domestic-studio-' + str(time.time_ns()))
        work.mkdir(mode=0o700)
        raw = json.dumps(data, sort_keys=True).encode()
        self.u.write(work / 'ledger.before.json', raw, exclusive=True)
        row = {'work': str(work), 'backend': str(roots['domestic']),
               'frontends': {k: str(v) for k, v in roots.items()}, 'schema': before['schema'],
               'ledger_before_sha256': self.u.digest(raw)}
        self.save(row, 'preparing')
        self.tool.save(self.flagged(data))
        paths.provision(self.u)
        with self.configure(row) as gateway:
            engine.prepare()
            gateway.preflight(data['current'])
        self.save(row, 'prepared')
        return row

    def deploy(self):
        row = self.read()
        if row['phase'] != 'prepared':
            raise RuntimeError('Joint transaction is not prepared; use recover')
        old = self.before(row)
        if self.tool.load() != self.flagged(old):
            raise RuntimeError('Joint ledger changed after preparation')
        snapshot.same(old['current'], self.tool.capture(self.flagged(old)))
        self.save(row, 'deploying')
        try:
            with self.configure(row):
                engine.apply()
            return self.finish()
        except BaseException:
            row = self.read()
            if row['phase'] not in marker.TERMINAL and row['phase'] != 'ledger-writing':
                self.save(row, 'forward-required' if snapshot.schemas(self.u) != row['schema'] else 'interrupted')
            raise

    def finish(self):
        row = self.read()
        if row['phase'] not in ('deploying', 'forward-required', 'verifying', 'ledger-writing', 'opening', 'complete'):
            raise RuntimeError('Joint transaction cannot be finalized in this phase')
        old = self.before(row)
        with self.configure(row, private_gateway=row['phase'] != 'complete') as gateway:
            opened_and_verified = False
            try:
                baseline = engine._read('prepared.json')
                joint_engine.check_migration(self.u, baseline, row['schema']['overseas'])
                if not (self.u.WORK / 'applied.json').exists():
                    raise RuntimeError('Candidate switch has not been verified')
                if gateway:
                    gateway.ensure_private()
                after = scope_snapshot.capture(self.u, runtime=True, domestic_publisher=True)
                if gateway:
                    after = gateway.normalize(after, old['current'])
                data = self.tool.load()
                if data == self.flagged(old):
                    if not gateway:
                        raise RuntimeError('Completed migration has an uncommitted ledger')
                    allowed = {str(self.u.COMPOSE), str(paths.TMPFILES)} | {str(engine._dropin(n)) for n in self.u.NATIVE}
                    completed = joint_state.advance(self.u, self.store, old, after, self.u.WORK,
                                                    row['backend'], row['frontends'], allowed)
                    row['after_sha256'] = catalog.state_sha(after)
                    self.save(row, 'ledger-writing')
                    self.tool.save(completed)
                else:
                    if (catalog.state_sha(after) != row.get('after_sha256') or data.get('migration_pending')
                            or data.get('pending')):
                        raise RuntimeError('Joint success ledger cannot be reconciled')
                    snapshot.same(data['current'], after)
                    catalog.check(data)
                if gateway:
                    self.save(row, 'opening')
                    gateway.open_public(after)
                    opened_and_verified = True
                    self.save(row, 'complete')
                return row
            except BaseException:
                if gateway and not opened_and_verified:
                    try:
                        gateway.seal()
                    except BaseException:
                        raise RuntimeError('Private ingress protection is unconfirmed; inspect the transaction') from None
                raise

    def recover(self):
        row, data = self.read(), self.tool.load()
        if row['phase'] == 'complete':
            return self.finish()
        if row['phase'] in ('rolled-back', 'cancelled'):
            return row
        old = self.before(row)
        self.configure(row)  # Bind WORK before acquiring the shared process fence.
        with fence.hold(self.u) as descriptor:
            work = Path(row['work'])
            if (work / 'domestic-migration.json').exists():
                with self.configure(row, external_fence=descriptor):
                    baseline = engine._read('prepared.json')
                    state = engine._load_state(baseline)
                    fence.wait_database(self.u, state['ctx']['hengxin-vps-codex-worker'])
            schemas = snapshot.schemas(self.u)
            if data != self.flagged(old):
                if (data == old and schemas == row['schema']
                        and (not (work / 'started.json').exists() or (work / 'rolled-back.json').exists())):
                    snapshot.same(old['current'], self.tool.capture(data, runtime=True))
                    self.save(row, 'rolled-back' if (work / 'started.json').exists() else 'cancelled')
                    return row
                if row['phase'] in ('ledger-writing', 'opening', 'forward-required'):
                    return self.finish()
                raise RuntimeError('Joint ledger changed during recovery')
            if schemas == row['schema']:
                with self.configure(row, external_fence=descriptor):
                    if (self.u.WORK / 'started.json').exists():
                        engine.recover()
                snapshot.same(old['current'], self.tool.capture(data, runtime=True))
                self.tool.save(old)
                self.save(row, 'rolled-back' if (work / 'started.json').exists() else 'cancelled')
                return row
            if schemas != dict(row['schema'], domestic='0043'):
                raise RuntimeError('Unrecognized schema drift; refusing all automatic recovery')
            with self.configure(row, external_fence=descriptor):
                forward.resume(row['schema']['overseas'])
            self.save(row, 'forward-required')
            return self.finish()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'deploy', 'recover', 'finish', 'status'))
    for name in scopes.GROUPS:
        parser.add_argument('--' + name, type=Path)
    args = parser.parse_args()
    if socket.gethostname() != 'hengxin-ai-245' or os.geteuid() != 0:
        raise RuntimeError('Only root on hengxin-ai-245 is supported')
    store = release.retention_store(Path('/var/lib/hengxin-release'))
    engine.u.safe(store.root)
    with store.locked():
        tool = Upgrade(store)
        if args.action == 'prepare':
            values = {name: getattr(args, name) for name in scopes.GROUPS}
            if not all(values.values()):
                parser.error('prepare requires three staged scoped releases')
            row = tool.prepare(values)
        else:
            row = tool.read() if args.action == 'status' else getattr(tool, args.action)()
        print(json.dumps({'phase': row['phase'], 'work': row['work']}))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        raise SystemExit('LAN_STUDIO_REFUSED: ' + (str(error) if isinstance(error, RuntimeError)
                                                   else type(error).__name__)) from None
