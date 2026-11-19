"""Argument routing for the existing release command, including scoped ledgers."""
import argparse
import json
from pathlib import Path


def run(cli, argv=None):
    parser = argparse.ArgumentParser(description=cli.__doc__)
    parser.add_argument('action', choices=('init', 'status', 'verify', 'prepare', 'prepare-fast', 'prepare-model', 'deploy', 'recover', 'rollback', 'cancel', 'cleanup', 'restore-ingress', 'tasks-prepare', 'tasks-deploy', 'tasks-recover', 'tasks-finish', 'tasks-status',
                                          'workspaces-prepare', 'workspaces-deploy', 'workspaces-recover',
                                          'workspaces-finish', 'workspaces-status',
                                          'general-prepare', 'general-deploy', 'general-recover', 'general-finish', 'general-status',
                                          'upload-apply', 'upload-rollback', 'upload-recover'))
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--release', type=Path)
    parser.add_argument('--mode', choices=('full', 'frontend'))
    parser.add_argument('--scope', choices=('domestic', 'overseas', 'shared'))
    args = parser.parse_args(argv)
    upload = args.action.startswith('upload-')
    if upload and (args.scope or args.mode or args.release or args.apply):
        parser.error('Domestic upload maintenance takes no options')
    args.mode = args.mode or 'full'
    if args.apply and args.action != 'cleanup':
        parser.error('--apply is only valid for cleanup')
    if args.release is not None and args.action not in ('prepare', 'prepare-fast', 'prepare-model', 'tasks-prepare', 'workspaces-prepare', 'general-prepare'):
        parser.error('--release is only valid for a preparation command')
    if args.action in ('prepare-fast', 'prepare-model') and (args.scope not in ('domestic', 'overseas') or args.mode != 'full'):
        parser.error(args.action + ' requires a domestic or overseas scope and cannot run frontend-only')
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
            from codex_runtime_marker import guard
            joint_studio_marker.guard(cli.engine.u, store)
            guard(cli.engine.u, store)
        tool = cli.Release(store)
        if not upload and args.action != 'status' and tool.path.exists():
            if (tool.load().get('pending') or {}).get('kind') == 'domestic-upload-gateway':
                raise RuntimeError('Resolve pending domestic gateway maintenance using upload-recover')
        if args.action.startswith('general-'):
            from domestic_tasks_release import run as maintenance_run
            import domestic_general_policy
            print(json.dumps(maintenance_run(store, args, domestic_general_policy), indent=2))
            return
        if args.action.startswith('workspaces-'):
            from domestic_tasks_release import run as maintenance_run
            import domestic_workspaces_policy
            print(json.dumps(maintenance_run(store, args, domestic_workspaces_policy), indent=2))
            return
        if args.action.startswith('tasks-'):
            from domestic_tasks_release import run as tasks_run
            print(json.dumps(tasks_run(store, args), indent=2))
            return
        if args.action != 'status':
            import domestic_tasks_marker
            domestic_tasks_marker.guard(cli.engine.u, store)
        if upload:
            from domestic_upload_maintenance import run as upload_run
            print(json.dumps(upload_run(tool, args.action.removeprefix('upload-')), indent=2))
            return
        if args.action == 'cleanup':
            tool.cleanup(apply=args.apply)
            return
        if args.action in ('prepare', 'prepare-fast', 'prepare-model'):
            if args.release is None:
                parser.error('prepare requires --release')
            if args.action == 'prepare-fast':
                data = tool.prepare(args.release, args.mode, args.scope, fast_maintenance=True)
            elif args.action == 'prepare-model':
                data = tool.prepare(args.release, 'backend', args.scope)
            else:
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
