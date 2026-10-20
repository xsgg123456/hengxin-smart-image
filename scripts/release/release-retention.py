"""CLI transaction boundary: verification first, independent best-effort GC last."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys


def module(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


s = module('release-retention-state')
d = module('release-retention-docker')
f = module('release-retention-failures')


def safe_cleanup(docker, data, store):
    try:
        f.retire(data, store, docker)
        docker.cleanup(data, store)
    except Exception as error:
        # Never propagate into a successful deployment's failure/stop handler.
        print('部署已验证成功；清理跳过或未完成：' + type(error).__name__, file=sys.stderr)


def receipt_path(store, release):
    s.require(isinstance(release, str) and s.RELEASE.fullmatch(release), 'Invalid release')
    path = store.root / ('verified-' + release + '.json')
    s.require(not path.is_symlink(), 'Success receipt must not be a symlink')
    return path


def finalize(store, docker, data, release):
    """Resume bookkeeping only, backed by a receipt written after main returned."""
    pending = data['pending'].get(release, {})
    s.require('before' in pending, 'No pending deployment to finalize')
    receipt = json.loads(receipt_path(store, release).read_text(encoding='utf-8'))
    s.require(receipt == {'release': release, 'before': pending['before'],
                          'image': pending.get('image')}, 'Success receipt mismatch')
    after = docker.snapshot()
    before = pending['before']
    for group in s.GROUPS:
        s.require(set(after[group]) == set(before[group]), 'Service topology drift')
        for service, identity in after[group].items():
            s.require(identity in (before[group][service], receipt['image']),
                      'Image drift since verified deployment: ' + group + '/' + service)
    s.advance(data, before, after)
    data['pending'].pop(release)
    data.setdefault('completed', {})[release] = after
    store.write(data)


def managed(main, argv=None, store=None, docker=None):
    args = sys.argv if argv is None else argv
    s.require(len(args) >= 3 and s.RELEASE.fullmatch(args[1]), 'Expected RELEASE ACTION')
    release, action = args[1:3]
    s.require(action in ('build', 'prepare', 'deploy', 'recover', 'resume'), 'Unknown managed action')
    s.require(not sys.flags.optimize, 'Python -O disables release safety assertions')
    store, docker = store or s.Store(), docker or d.Docker()
    with store.locked():
        data = store.load()
        if f.seed_legacy(data):
            store.write(data)
        pending = data['pending'].get(release, {})
        completed = data.get('completed', {})
        if release in completed:
            s.require(action in ('deploy', 'recover', 'resume') and
                      docker.snapshot() == completed[release], 'Release already completed or fleet changed')
            safe_cleanup(docker, data, store)
            return
        if action in ('deploy', 'recover', 'resume') and receipt_path(store, release).exists():
            finalize(store, docker, data, release)
            safe_cleanup(docker, data, store)
            return
        if action in ('recover', 'resume'):
            s.require('before' in pending, 'Recovery requires the saved failed-deployment snapshot')
            before = pending['before']
        elif action == 'deploy':
            s.require('before' not in pending, 'Interrupted deployment: use recovery')
            before = docker.snapshot()
        else:
            s.require('before' not in pending, 'Cannot rebuild a deployment pending recovery')
            before = None
        if before:
            for group, history in data['groups'].items():
                s.require(history['current'] == before[group], 'Current version drift: ' + group)
            pending['before'] = before
        pending.update(phase='deploy' if before else action, image=docker.candidate(release))
        data['pending'][release] = pending
        store.write(data)
        try:
            result = main()
        except BaseException:
            pending['phase'] = 'failed'
            f.record(data, release)
            store.write(data)
            raise
        if before is None:
            pending.update(phase='built' if action == 'build' else 'prepared', image=docker.candidate(release))
            store.write(data)
            return result
        # No deployment failure handlers surround this post-verification section.
        try:
            store.report(receipt_path(store, release).name,
                         {'release': release, 'before': before, 'image': pending['image']})
            finalize(store, docker, data, release)
        except Exception as error:
            print('部署返回成功，但版本台账未确认，禁止清理：' + type(error).__name__, file=sys.stderr)
            return result
        safe_cleanup(docker, data, store)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('init', 'preview', 'cleanup', 'abandon', 'finalize'))
    for group in s.GROUPS:
        parser.add_argument('--' + group + '-previous')
    parser.add_argument('--release')
    args = parser.parse_args()
    store, docker = s.Store(), d.Docker()
    with store.locked():
        data = store.load()
        if args.action == 'init':
            live = docker.snapshot()
            s.require(not any('before' in pending for pending in data['pending'].values()),
                      'Resolve interrupted deployment before initialization')
            for group in s.GROUPS:
                old = data['groups'].get(group)
                if old:
                    s.require(old['current'] == live[group], 'Current version drift: ' + group)
                    if old['previous']:
                        continue  # Initialization may fill gaps; never overwrite history.
                ref = getattr(args, group + '_previous')
                s.require(ref, 'Explicit previous successful image required: ' + group)
                image = docker.resolve(ref)
                data['groups'][group] = {'current': live[group],
                                         'previous': {service: image for service in live[group]}}
            store.write(data)
        elif args.action == 'finalize':
            finalize(store, docker, data, args.release)
            safe_cleanup(docker, data, store)
        elif args.action == 'abandon':
            s.require(args.release in data['pending'], 'Unknown pending release')
            s.require(not receipt_path(store, args.release).exists(), 'Verified release requires finalize')
            docker.plan(data)  # Require initialized, healthy and unchanged fleet.
            del data['pending'][args.release]
            store.write(data)
        elif args.action == 'preview':
            plan = docker.plan(data)
            plan['retire_failed'] = f.preview(data, store, docker)
            print(json.dumps(plan, indent=2))
        else:
            f.retire(data, store, docker)
            docker.cleanup(data, store)


if __name__ == '__main__':
    main()
