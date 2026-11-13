"""Argument routing for the existing release command, including scoped ledgers."""
import argparse
import json
from pathlib import Path


def run(cli, argv=None):
    parser = argparse.ArgumentParser(description=cli.__doc__)
    parser.add_argument('action', choices=('init', 'status', 'verify', 'prepare', 'deploy', 'recover', 'rollback', 'cancel', 'cleanup', 'restore-ingress'))
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--release', type=Path)
    parser.add_argument('--mode', choices=('full', 'frontend'), default='full')
    parser.add_argument('--scope', choices=('domestic', 'overseas', 'shared'))
    args = parser.parse_args(argv)
    if args.apply and args.action != 'cleanup':
        parser.error('--apply is only valid for cleanup')
    if args.release is not None and args.action != 'prepare':
        parser.error('--release is only valid for prepare')
    if cli.socket.gethostname() != 'hengxin-ai-245' or cli.os.geteuid() != 0:
        raise RuntimeError('Only root on hengxin-ai-245 is supported')
    cli.engine.u.safe(cli.engine.u.ROOT)
    store = cli.retention_store(Path('/var/lib/hengxin-release'))
    cli.engine.u.safe(store.root)
    with store.locked():
        marker = store.root/'intranet-split-migration.json'
        if marker.exists():
            cli.engine.u.safe(marker)
            if json.loads(marker.read_bytes())['phase'] not in ('complete', 'rolled-back') and args.action != 'status':
                raise RuntimeError('Resolve the recorded split migration before publishing')
        if args.action != 'status':
            import joint_studio_marker
            joint_studio_marker.guard(cli.engine.u, store)
        tool = cli.Release(store)
        if args.action == 'cleanup':
            tool.cleanup(apply=args.apply)
            return
        if args.action == 'prepare':
            if args.release is None:
                parser.error('prepare requires --release')
            data = tool.prepare(args.release, args.mode, args.scope)
        elif args.action in ('status', 'verify'):
            data = tool.load()
            if args.action == 'verify':
                cli.snapshot.same(data['current'], tool.capture(data, runtime=True))
                cli.catalog.before(cli.engine.u, store, data)
        elif args.action == 'restore-ingress':
            from restore_ingress import restore
            data = restore(tool)
        elif args.action == 'rollback':
            data = tool.rollback(args.scope)
        else:
            if args.scope:
                existing = tool.load()
                if (existing.get('pending') or {}).get('scope') != args.scope:
                    raise RuntimeError('Pending release does not match requested scope')
            data = getattr(tool, args.action)()
        if data['version'] == 2:
            from scope_release import summary
            result = {'action': args.action, 'groups': summary(data)}
        else:
            result = {'action': args.action, 'backend_commit': data['current']['backend_commit'],
                      'frontend_commit': data['current']['frontend_commit'], 'previous': bool(data['previous'])}
        result['pending'] = data['pending']['phase'] if data['pending'] else None
        print(json.dumps(result, indent=2))
