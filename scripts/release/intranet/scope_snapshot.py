"""Verify independently mounted sources using the existing snapshot primitives."""
import json
import os
from pathlib import Path
import urllib.request

import image_gc
import scopes
import snapshot


CODE = ("import pathlib,json,hashlib; r=pathlib.Path('/app'); "
        "print(json.dumps({p.relative_to(r).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() "
        "for p in (r/'app').rglob('*') if p.is_file() and '__pycache__' not in p.parts}))")
PACKAGES = 'import importlib.metadata as m,json; print(json.dumps(sorted((d.metadata["Name"],d.version) for d in m.distributions())))'
BINARY = ("from app.core.config import get_settings; import pathlib,hashlib,json; "
          "s=get_settings(); paths=[pathlib.Path(s.codex_binary).resolve(),pathlib.Path(s.codex_bwrap_binary).resolve()]; "
          "print(json.dumps({str(p):hashlib.file_digest(p.open('rb'),'sha256').hexdigest() for p in paths}))")


def containers(u, domestic_publisher=False):
    apps = (*u.APPS, *scopes.UI.values(), *((scopes.DOMESTIC_PUBLISHER,) if domestic_publisher else ()))
    with scopes.replace(u, APPS=tuple(dict.fromkeys(apps))):
        return u.containers()


def config_paths(u, live=None):
    """Enumerate unit/env config plus every nginx bind, including gateway/TLS.

    Bind directories are expanded to files; unknown writable nginx mounts refuse.
    Frontend content mounts are source artifacts, not configuration files.
    """
    paths = set(u.config_paths())
    live = containers(u) if live is None else live
    for name in ('domestic-web', *scopes.UI.values()):
        for mount in live[name]['Mounts']:
            target = mount['Destination']
            if target == '/etc/nginx' or target.startswith('/etc/nginx/'):
                if mount.get('RW') or mount.get('Type', 'bind') != 'bind':
                    raise RuntimeError('Expected read-only nginx configuration bind')
                root = Path(mount['Source'])
                u.safe(root)
                if root.is_dir():
                    for path in root.rglob('*'):
                        u.safe(path)
                        if path.is_file():
                            paths.add(path)
                else:
                    paths.add(root)
    if scopes.DOMESTIC_PUBLISHER in live:
        from joint_studio_paths import TMPFILES
        paths.add(TMPFILES)
    for path in paths:
        u.safe(path)
    return sorted(paths)


def verify_frontend(scope, manifest):
    with urllib.request.urlopen(f'http://192.168.1.245:8080/{scope}/', timeout=10) as response:
        if response.status != 200 or snapshot.sha(response.read()) != manifest['files']['frontend/index.html']:
            raise RuntimeError('Served frontend differs from release: ' + scope)


def capture(u, runtime=False, domestic_publisher=False):
    live, ctx = containers(u, domestic_publisher), u.contexts()
    if domestic_publisher:
        from joint_studio_verify import runtime as verify_studio
        verify_studio(u, live, ctx)
    groups, identities, binaries, fallbacks = {}, {}, {}, {}
    for scope in scopes.GROUPS:
        backends = {snapshot.mounted(live[n], '/app/app').parent.parent for n in scopes.apps(scope, domestic_publisher)}
        if len(backends) != 1:
            raise RuntimeError('Group containers run mixed sources: ' + scope)
        backend = snapshot.release_path(backends.pop())
        frontend = snapshot.release_path(snapshot.mounted(live[scopes.UI[scope]], '/usr/share/nginx/html').parent)
        bm, fm = snapshot.manifest(u, backend), snapshot.manifest(u, frontend)
        prior_mounts = [v for v in live[scopes.UI[scope]]['Mounts'] if v['Destination'] == '/usr/share/nginx/previous']
        if len(prior_mounts) != 1 or prior_mounts[0].get('RW') or prior_mounts[0].get('Type', 'bind') != 'bind':
            raise RuntimeError('Expected read-only previous frontend bind')
        prior = snapshot.release_path(snapshot.mounted(live[scopes.UI[scope]], '/usr/share/nginx/previous').parent)
        if Path(prior_mounts[0]['Source']) != prior/'frontend':
            raise RuntimeError('Unexpected previous frontend source')
        snapshot.manifest(u, prior)
        fallbacks[scope] = {'source': str(prior), 'manifest': snapshot.sha((prior/'release-manifest.json').read_bytes())}
        expected = {n.removeprefix('backend/'): h for n, h in bm['files'].items() if n.startswith('backend/app/')}
        for name in scopes.apps(scope, domestic_publisher):
            actual = json.loads(u.run(['docker', 'exec', 'hengxin-lan-' + name, 'python', '-B', '-c', CODE]))
            if actual != expected:
                raise RuntimeError('Live source mismatch: ' + name)
        for name in scopes.NATIVE[scope]:
            value = ctx[name]
            if value['cwd'] != str(backend / 'backend') or os.readlink('/proc/' + u.prop(name, 'MainPID') + '/cwd') != str(backend / 'backend'):
                raise RuntimeError('Native process source mismatch: ' + name)
            identities[name] = {k: value[k] for k in ('python', 'user', 'group', 'extra_groups')}
            identities[name]['packages'] = snapshot.sha(u.native_run(value, code=PACKAGES).encode())
        verify_frontend(scope, fm)
        groups[scope] = {'backend': str(backend), 'frontend': str(frontend),
                         'backend_commit': bm['commit'], 'frontend_commit': fm['commit'],
                         'backend_manifest': snapshot.sha((backend / 'release-manifest.json').read_bytes()),
                         'frontend_manifest': snapshot.sha((frontend / 'release-manifest.json').read_bytes())}
    for name in u.WORKERS[:2]:
        if runtime:
            u.native_run(ctx[name], module='app.execution.runtime_check')
        binaries[name] = json.loads(u.native_run(ctx[name], code=BINARY))
    u.health(ctx, frontend=True)
    for name in scopes.UI.values():
        info = live[name]
        if not info['State']['Running'] or info['State'].get('Health', {}).get('Status', 'healthy') != 'healthy':
            raise RuntimeError('Static service not healthy: ' + name)
    return {'groups': groups, 'asset_fallbacks': fallbacks,
            'images': image_gc.capture(image_gc.scoped(u, domestic_publisher)),
            'native': identities, 'binaries': binaries, 'schema': snapshot.schemas(u), 'data': u.data_identity(),
            'configs': {str(p): snapshot.sha(p.read_bytes()) for p in config_paths(u, live)}}


def group(state, scope):
    scopes.validate(scope)
    result = dict(state['groups'][scope])
    result.update(images={n: state['images'][n] for n in (*scopes.apps(scope, scopes.has_domestic_publisher(state)), scopes.UI[scope])},
                  native={n: state['native'][n] for n in scopes.NATIVE[scope]},
                  binaries={n: state['binaries'][n] for n in scopes.WORKERS[scope] if n in state['binaries']},
                  schema={scope: state['schema'][scope]} if scope != 'shared' else {})
    return result


def census(u, independent=True, domestic_publisher=False):
    """Read-only identity/start-time evidence; includes gateway, static and DATA."""
    adapter = image_gc.scoped(u, domestic_publisher) if independent else u
    inventory = image_gc.containers(adapter)
    names = image_gc.live(adapter, inventory)
    live = {v['Config']['Labels']['com.docker.compose.service']: v for v in inventory
            if v['Name'].removeprefix('/') in {'hengxin-lan-' + n for n in names}}
    return {'containers': {n: {'id': v['Id'], 'started': v['State']['StartedAt']} for n, v in live.items()},
            'native': {n: {'pid': u.prop(n, 'MainPID'),
                           'started': u.prop(n, 'ExecMainStartTimestampMonotonic')} for n in u.NATIVE}}


def unchanged_other(before, after, scope, mode='full'):
    """Prove service identities, not just source/mount equality, stayed stable."""
    scopes.validate(scope, mode)
    publisher = scopes.DOMESTIC_PUBLISHER in before['containers']
    excluded_apps = set(scopes.apps(scope, publisher)) if mode == 'full' else set()
    excluded_apps.add(scopes.UI[scope])
    excluded_native = set(scopes.NATIVE[scope]) if mode == 'full' else set()
    for section, excluded in (('containers', excluded_apps), ('native', excluded_native)):
        first = {n: v for n, v in before[section].items() if n not in excluded}
        second = {n: v for n, v in after[section].items() if n not in excluded}
        if first != second:
            raise RuntimeError('Unaffected runtime changed: ' + section)
