"""Reversible static-only migration; no backend, queue or data mutations."""
import argparse
import json
from pathlib import Path
import time

import catalog
import engine
import release
import scope_snapshot
import scopes
import snapshot
import split_config
import split_state

NAME = 'intranet-split-migration.json'


class Migration:
    def __init__(self, store):
        self.store, self.u = store, engine.u
        self.tool = release.Release(store)

    def read(self):
        path = self.store.root/NAME
        self.u.safe(path)
        return json.loads(path.read_bytes())

    def save(self, row, phase):
        row['phase'] = phase
        self.store.report(NAME, row)

    def bytes(self, row, name):
        path = Path(row['work'])/name
        self.u.safe(path)
        raw = path.read_bytes()
        if snapshot.sha(raw) != row['files'][name]:
            raise RuntimeError('Migration backup/candidate drift')
        return raw

    def prepare(self, releases):
        if (self.store.root/NAME).exists():
            raise RuntimeError('Migration record exists; finish or roll back that record')
        data = self.tool.load()
        if data['version'] != 1 or data['pending']:
            raise RuntimeError('Migration requires an idle verified legacy baseline')
        snapshot.same(data['current'], snapshot.capture(self.u, runtime=True))
        data = catalog.before(self.u, self.store, data)
        split_state.check_packages(self.u, data['current'], releases)
        for path in releases.values():
            if str(path) not in data['retention']['staged']:
                raise RuntimeError('Migration packages must first be staged through stage.py')
        before = scope_snapshot.census(self.u, independent=False)
        nginx = self.u.ROOT/'nginx.conf'
        self.u.safe(nginx)
        original = self.u.COMPOSE.read_bytes()
        config = split_config.compose(self.u, json.loads(original), releases)
        parent = self.store.root/'intranet-transactions'
        parent.mkdir(mode=0o700, exist_ok=True)
        self.u.safe(parent)
        work = parent/('split-' + str(time.time_ns()))
        work.mkdir(mode=0o700)
        content = {'ledger.before.json': json.dumps(data).encode(), 'compose.before.json': original,
                   'nginx.before.conf': nginx.read_bytes(),
                   'compose.candidate.json': json.dumps(config, indent=2).encode(),
                   'nginx.candidate.conf': split_config.gateway(nginx.read_bytes())}
        for name, raw in content.items():
            self.u.write(work/name, raw, exclusive=True)
        row = {'work': str(work), 'releases': {s: str(p) for s, p in releases.items()},
               'files': {n: snapshot.sha(b) for n, b in content.items()}, 'before': before,
               'nginx_identity': [nginx.stat().st_dev, nginx.stat().st_ino]}
        self.save(row, 'prepared')
        return row

    def same_original(self, row, with_ui):
        after = scope_snapshot.census(self.u, independent=with_ui)
        split_state.unchanged_original(row['before'], after)

    def apply(self):
        row = self.read()
        if row['phase'] != 'prepared':
            raise RuntimeError('Interrupted migration: use finish after a verified gateway switch, otherwise rollback')
        old = json.loads(self.bytes(row, 'ledger.before.json'))
        self.same_original(row, False)
        if self.u.COMPOSE.read_bytes() != self.bytes(row, 'compose.before.json'):
            raise RuntimeError('Concurrent compose change before migration')
        if self.tool.load() != old:
            raise RuntimeError('Concurrent release ledger change before migration')
        work = Path(row['work'])
        self.bytes(row, 'compose.candidate.json')
        self.save(row, 'ui-starting')
        for scope in scopes.GROUPS:
            path, content = self.u.ROOT/(scope+'-ui.conf'), split_config.ui_config(scope)
            if path.exists():
                self.u.safe(path)
                if path.read_bytes() != content:
                    raise RuntimeError('Existing scoped nginx configuration differs')
            else:
                self.u.write(path, content, mode=0o644, exclusive=True)
        self.u.compose('config', '--quiet', config=work/'compose.candidate.json')
        self.u.compose('up', '-d', '--no-deps', '--pull', 'never', *scopes.UI.values(), config=work/'compose.candidate.json')
        self.same_original(row, True)
        self.save(row, 'ui-ready')
        candidate = self.bytes(row, 'nginx.candidate.conf')
        split_config.check_gateway(self.u, work/'nginx.candidate.conf', json.loads(self.bytes(row, 'compose.before.json')))
        self.save(row, 'gateway-switching')
        try:
            self.u.write(self.u.COMPOSE, self.bytes(row, 'compose.candidate.json'))
            split_config.bound_write(self.u, self.u.ROOT/'nginx.conf', candidate, row['files']['nginx.before.conf'])
            split_config.reload_gateway(self.u)
            self.save(row, 'gateway-switched')
            return self.finish()
        except BaseException:
            self.rollback()
            raise

    def finish(self):
        row = self.read()
        if row['phase'] not in ('gateway-switched', 'ledger-written', 'complete'):
            raise RuntimeError('Gateway switch is not verified; roll back before retrying')
        if self.u.COMPOSE.read_bytes() != self.bytes(row, 'compose.candidate.json'):
            raise RuntimeError('Migration compose drift')
        if (self.u.ROOT/'nginx.conf').read_bytes() != self.bytes(row, 'nginx.candidate.conf'):
            raise RuntimeError('Migration gateway drift')
        self.same_original(row, True)
        after = scope_snapshot.capture(self.u, runtime=True)
        if row['phase'] == 'complete':
            snapshot.same(self.tool.load()['current'], after)
            return row
        old = json.loads(self.bytes(row, 'ledger.before.json'))
        data = split_state.initialize(self.u, self.store, old, after, Path(row['work']))
        self.tool.save(data)
        self.save(row, 'ledger-written')
        self.same_original(row, True)
        data['migration_pending'] = False
        self.tool.save(data)
        self.save(row, 'complete')
        return row

    def rollback(self):
        row = self.read()
        old = json.loads(self.bytes(row, 'ledger.before.json'))
        current = self.tool.load()
        if current['version'] == 2 and any(v['current_work'] != row['work'] for v in current['groups'].values()):
            raise RuntimeError('Independent releases already advanced; use per-scope rollback')
        nginx = self.u.ROOT/'nginx.conf'
        self.u.safe(nginx)
        if [nginx.stat().st_dev, nginx.stat().st_ino] != row['nginx_identity']:
            raise RuntimeError('Gateway bind identity changed')
        original, candidate = self.bytes(row, 'nginx.before.conf'), self.bytes(row, 'nginx.candidate.conf')
        actual = nginx.read_bytes()
        if actual not in (original, candidate):
            # A crash may leave a prefix of the verified in-place write. Do not
            # overwrite unrelated bytes under the guise of recovery.
            partial = row['phase'] == 'gateway-switching' and any(
                actual == candidate[:n] + original[n:] or actual == candidate[:n]
                for n in range(len(candidate) + 1))
            if not partial:
                raise RuntimeError('Concurrent gateway drift prevents migration rollback')
        if self.u.COMPOSE.read_bytes() not in (self.bytes(row, 'compose.before.json'), self.bytes(row, 'compose.candidate.json')):
            raise RuntimeError('Concurrent compose drift prevents migration rollback')
        split_config.bound_write(self.u, nginx, original, snapshot.sha(actual))
        split_config.reload_gateway(self.u)
        # Only stateless containers created by this migration may be removed.
        for scope, service in scopes.UI.items():
            ids = self.u.run(['docker', 'ps', '-aq', '--filter', 'name=^hengxin-lan-'+service+'$']).split()
            if not ids:
                continue
            if len(ids) != 1:
                raise RuntimeError('Ambiguous migration static container')
            info = json.loads(self.u.run(['docker', 'inspect', ids[0]]))[0]
            labels = info['Config']['Labels']
            if labels.get('com.docker.compose.project') != 'hengxin-lan' or labels.get('com.docker.compose.service') != service:
                raise RuntimeError('Foreign static container blocks rollback')
            if snapshot.mounted(info, '/usr/share/nginx/html') != Path(row['releases'][scope])/'frontend':
                raise RuntimeError('Static container source changed')
            self.u.run(['docker', 'stop', '--timeout', '-1', ids[0]], timeout=180)
            self.u.run(['docker', 'rm', ids[0]])
        self.u.write(self.u.COMPOSE, self.bytes(row, 'compose.before.json'))
        self.tool.save(old)
        snapshot.same(old['current'], snapshot.capture(self.u, runtime=True))
        self.same_original(row, False)
        self.save(row, 'rolled-back')
        return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'apply', 'finish', 'rollback', 'status'))
    for scope in scopes.GROUPS:
        parser.add_argument('--'+scope, type=Path)
    args = parser.parse_args()
    if release.socket.gethostname() != 'hengxin-ai-245' or release.os.geteuid() != 0:
        raise RuntimeError('Only root on hengxin-ai-245 is supported')
    store = release.retention_store(Path('/var/lib/hengxin-release'))
    engine.u.safe(store.root)
    with store.locked():
        tool = Migration(store)
        if args.action == 'prepare':
            values = {s: getattr(args, s) for s in scopes.GROUPS}
            if not all(values.values()):
                parser.error('prepare requires all three staged scope releases')
            row = tool.prepare(values)
        else:
            row = tool.read() if args.action == 'status' else getattr(tool, args.action)()
        print(json.dumps({'phase': row['phase'], 'work': row['work']}))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        raise SystemExit('LAN_SPLIT_REFUSED: ' + (str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__)) from None
