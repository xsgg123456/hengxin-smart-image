"""Bind one group to engine.prepare/apply/recover under the existing host lock."""
from contextlib import contextmanager, ExitStack
import copy
import json
from pathlib import Path

import engine
import scopes
from scope_actions import Actions


def candidate(original, u, scope, mode, backend, frontend):
    scopes.validate(scope, mode)
    result = copy.deepcopy(original)
    expected = {n for names in scopes.APPS.values() for n in names} | set(scopes.UI.values()) | {'domestic-web'} | u.DATA
    if result.get('name') != 'hengxin-lan' or set(result['services']) != expected:
        raise RuntimeError('Independent compose inventory changed')
    for name in scopes.APPS[scope] if mode == 'full' else ():
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
def context(scope, mode='full', backend=None, frontend=None):
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
    binding = {'scope': scope, 'mode': mode, 'backend': str(backend), 'frontend': str(frontend)}
    actions = Actions(u, scope, mode, original, all_native, backend)
    native = {n: all_native[n] for n in scopes.NATIVE[scope]} if mode == 'full' else {}
    python = {n: u.PYTHON_SERVICES[n] for n in scopes.APPS[scope]} if mode == 'full' else {}

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
                  candidate_compose=lambda c: candidate(c, u, scope, mode, backend, frontend))
    with ExitStack() as stack:
        stack.enter_context(scopes.replace(u, **values))
        stack.enter_context(scopes.replace(engine, _quiesce=actions.quiesce,
                                           prepare=prepare_scoped, _check=check_scoped))
        yield
