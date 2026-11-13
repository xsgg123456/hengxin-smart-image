"""Bind one group to engine.prepare/apply/recover under the existing host lock."""
from contextlib import contextmanager, ExitStack
import copy
import json
import re
from pathlib import Path

import engine
import scopes
from scope_actions import Actions


def native_dropin(original, backend):
    """Change only the source directory; retain the verified service settings."""
    sections = re.findall(rb'^\s*(\[[^\r\n]+\])\s*$', original, re.MULTILINE)
    pattern = rb'^WorkingDirectory=[^\r\n]*(?:\r?\n|$)'
    assignments = re.findall(rb'^[ \t]*WorkingDirectory[ \t]*=', original, re.MULTILINE)
    if (not original.startswith((b'[Service]\n', b'[Service]\r\n'))
            or sections != [b'[Service]'] or len(assignments) != 1
            or len(re.findall(pattern, original, re.MULTILINE)) != 1
            or re.search(rb'\\\r?\n', original)):
        raise RuntimeError('Unexpected native source drop-in structure')
    replacement = ('WorkingDirectory=' + str(backend / 'backend') + '\n').encode()
    return re.sub(pattern, lambda _: replacement, original, flags=re.MULTILINE)


def candidate(original, u, scope, mode, backend, frontend, domestic_publisher=False):
    scopes.validate(scope, mode)
    result = copy.deepcopy(original)
    expected = {n for names in scopes.APPS.values() for n in names} | set(scopes.UI.values()) | {'domestic-web'} | u.DATA
    if domestic_publisher:
        expected.add(scopes.DOMESTIC_PUBLISHER)
    if result.get('name') != 'hengxin-lan' or set(result['services']) != expected:
        raise RuntimeError('Independent compose inventory changed')
    for name in scopes.apps(scope, domestic_publisher) if mode == 'full' else ():
        service = result['services'][name]
        mounts = service.get('volumes', [])
        if any(not isinstance(v, dict) or 'target' not in v for v in mounts):
            raise RuntimeError('Only explicit compose mounts supported')
        if any(v['target'] in ('/', '/app') for v in mounts):
            raise RuntimeError('Unexpected parent code mount')
        service['volumes'] = [v for v in mounts if not (v['target'] == '/app/app' or v['target'].startswith('/app/app/'))]
        service['volumes'].append({'type': 'bind', 'source': str(backend / 'backend/app'),
                                  'target': '/app/app', 'read_only': True, 'bind': {'create_host_path': False}})
    mounts = result['services'][scopes.UI[scope]].get('volumes', [])
    matched = [v for v in mounts if isinstance(v, dict) and v.get('target') == '/usr/share/nginx/html']
    if len(matched) != 1 or not matched[0].get('read_only'):
        raise RuntimeError('Unexpected scoped frontend mount')
    fallback = [v for v in mounts if isinstance(v, dict) and v.get('target') == '/usr/share/nginx/previous']
    if len(fallback) > 1 or any(v.get('type') != 'bind' or not v.get('read_only') for v in fallback):
        raise RuntimeError('Unexpected previous frontend mount')
    # The outgoing current build remains available even when the target is an
    # immutable older rollback version. Never edit that historical artifact.
    previous = {'type': 'bind', 'source': matched[0]['source'],
                'target': '/usr/share/nginx/previous', 'read_only': True,
                'bind': {'create_host_path': False}}
    if fallback:
        mounts.remove(fallback[0])
    mounts.append(previous)
    matched[0]['source'] = str(frontend / 'frontend')
    return result


@contextmanager
def context(scope, mode='full', backend=None, frontend=None, domestic_publisher=False):
    """No I/O on entry; prepare persists scope identity in release_manifest.

    backend/frontend are release roots, not backend/frontend subdirectories.
    A rollback starts a fresh prepare from the current full compose, never a
    previous transaction's global compose backup. Recovery uses its own backup.
    """
    scopes.validate(scope, mode)
    if scope == 'shared' and mode == 'full':
        raise RuntimeError('Shared backend release requires a separate joint maintenance plan')
    u = engine.u
    backend, frontend = Path(backend or u.RELEASE), Path(frontend or u.RELEASE)
    all_native = u.NATIVE
    names = ('contexts', 'drain', 'gate_accounts', 'stop_apps', 'start_apps', 'health',
             'probe_candidate', 'app_command', 'remove_stop_overrides', 'validate_release')
    original = {n: getattr(u, n) for n in names}
    prepare, check = engine.prepare, engine._check
    binding = {'scope': scope, 'mode': mode, 'backend': str(backend), 'frontend': str(frontend),
               'domestic_publisher': domestic_publisher}
    actions = Actions(u, scope, mode, original, all_native, backend)
    native = {n: all_native[n] for n in scopes.NATIVE[scope]} if mode == 'full' else {}
    modules = dict(u.PYTHON_SERVICES)
    modules[scopes.DOMESTIC_PUBLISHER] = 'app.modules.domestic_studio.skill_publisher'
    python = {n: modules[n] for n in scopes.apps(scope, domestic_publisher)} if mode == 'full' else {}

    def validate_release():
        manifests = {}
        for root in sorted({backend, frontend}):
            with scopes.replace(u, RELEASE=root):
                manifests[str(root)] = original['validate_release']()
        return u.digest(json.dumps({'scope': scope, 'mode': mode, 'backend': str(backend),
                                    'frontend': str(frontend), 'manifests': manifests}, sort_keys=True).encode())

    def prepare_scoped():
        result = prepare()
        baseline = engine._read('prepared.json')
        originals = {row['path']: row for row in baseline['configs']}
        for name in u.NATIVE:
            row = originals.get(str(engine._dropin(name)))
            if row:
                data = native_dropin((u.WORK / row['backup']).read_bytes(), backend)
                u.write(u.WORK / (name + '.conf'), data)
                baseline['dropins'][name] = u.digest(data)
        baseline['scope_binding'] = binding
        engine._save('prepared.json', baseline)
        return result

    def check_scoped(baseline, recovering=False, state=None):
        if baseline.get('scope_binding') != binding:
            raise RuntimeError('Transaction scope binding differs')
        return check(baseline, recovering=recovering, state=state)

    values = {n: getattr(actions, n) for n in names if hasattr(actions, n)}
    values.update(NATIVE=native, PYTHON_SERVICES=python, APPS=(*python, scopes.UI[scope]),
                  ENTRIES=tuple(n for n in python if n.endswith('-api')) + (scopes.UI[scope],),
                  RELEASE=backend, validate_release=validate_release,
                  candidate_compose=lambda c: candidate(c, u, scope, mode, backend, frontend, domestic_publisher))
    with ExitStack() as stack:
        stack.enter_context(scopes.replace(u, **values))
        stack.enter_context(scopes.replace(engine, _quiesce=actions.quiesce,
                                           prepare=prepare_scoped, _check=check_scoped))
        yield
