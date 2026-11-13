"""Build one immutable candidate for the reviewed three-scope Studio upgrade."""
from pathlib import PurePosixPath

import domestic_studio_wiring as wiring
import joint_studio_gate_wiring as gate_wiring
import scope_engine
import scopes


def release_root(value):
    root = PurePosixPath(str(value))
    if (root.parent != PurePosixPath('/opt/hengxin-unified-releases')
            or root.name.startswith('.') or not root.name or '..' in root.parts):
        raise ValueError('Invalid immutable release root')
    return root


def candidate(original, u, backend, frontends):
    """Keep infrastructure untouched and bind all app code to one backend."""
    root = release_root(backend)
    if set(frontends) != set(scopes.GROUPS):
        raise ValueError('All three frontend releases are required')
    versions = {scope: release_root(frontends[scope]) for scope in scopes.GROUPS}
    if len(set(versions.values())) != len(scopes.GROUPS):
        raise ValueError('Each scope requires its own frontend release')
    result = original
    for scope in scopes.GROUPS:
        result = scope_engine.candidate(result, u, scope, 'full', root, versions[scope])
    return gate_wiring.candidate(wiring.candidate(result, root))


def native_dropin(name, backend):
    """Preserve service commands; the native worker and cleanup share host paths."""
    root = release_root(backend)
    value = '[Service]\nWorkingDirectory=' + str(root / 'backend') + '\n'
    if name in {'hengxin-vps-codex-worker', 'hengxin-domestic-deletions'}:
        for key, item in sorted(wiring.native_environment().items()):
            value += 'Environment=' + key + '=' + item + '\n'
    if name in gate_wiring.NATIVE:
        value += 'Environment=' + gate_wiring.ENVIRONMENT + '=' + gate_wiring.DIRECTORY + '\n'
    return value.encode()
