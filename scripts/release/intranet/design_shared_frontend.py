"""Publish the login bundle paired with the completed overseas design migration."""
import hashlib
import json
from pathlib import Path

import catalog
import scope_changes
import scope_release
import scopes
import snapshot


COMMIT = '133f16ae213b1c39f1a4c8b8556a2feb7fb28d49'
SHARED_BASE = '2bc8acc7ecf412626a6a635a9413b1644b55417e'
SHARED_ASSETS = '54bc121f728d972cf90103939c744d09bf611a4116f578c31ee1ba0b4433495d'


def validate(ledger, overseas, candidate):
    groups = ledger['groups']
    shared = groups['shared']['current']
    design = groups['overseas']['current']
    if (ledger.get('pending') or ledger.get('migration_pending')
            or shared['backend_commit'] != SHARED_BASE or shared['frontend_commit'] != SHARED_BASE
            or design['frontend_commit'] != COMMIT or design['backend_commit'] != COMMIT
            or design['schema'] != {'overseas': 'overseas_0028'}):
        raise RuntimeError('Shared design login requires the completed overseas release and original shared baseline')
    for manifest, scope in ((overseas, 'overseas'), (candidate, 'shared')):
        provenance = manifest['provenance']
        if (manifest.get('scope') != scope or manifest['commit'] != COMMIT
                or provenance['source_commit'] != COMMIT
                or provenance['build']['environment'].get('VITE_RELEASE_SCOPE') != scope):
            raise RuntimeError('Unexpected release source or bundle scope')
    assets = candidate.get('frontend_current_files', {})
    if (hashlib.sha256(json.dumps(assets, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
            != SHARED_ASSETS or any(candidate['files'].get(name) != digest for name, digest in assets.items())):
        raise RuntimeError('Shared frontend build differs from the audited package')
    if (not overseas['provenance']['source_files']
            or candidate['provenance']['source_files'] != overseas['provenance']['source_files']
            or not scope_changes.backend_files(overseas)
            or scope_changes.backend_files(candidate) != scope_changes.backend_files(overseas)
            or candidate['runtime_inputs'] != overseas['runtime_inputs']):
        raise RuntimeError('Shared login and verified overseas package inputs differ')


def prepare(tool, release):
    candidate_root = snapshot.release_path(release)
    ledger = tool.load()
    if str(candidate_root) not in catalog.check(ledger)['staged']:
        raise RuntimeError('Shared login candidate must be staged through the release ledger')
    shared_root = Path(ledger['groups']['shared']['current']['backend'])
    overseas_root = Path(ledger['groups']['overseas']['current']['backend'])
    validate(ledger, snapshot.manifest(tool.u, overseas_root), snapshot.manifest(tool.u, candidate_root))

    def check(u, before_root, after_root, scope, mode, fast_maintenance=False):
        if ((u, before_root, after_root, scope, mode, fast_maintenance)
                != (tool.u, shared_root, candidate_root, 'shared', 'frontend', False)):
            raise RuntimeError('Only the shared frontend may be switched')
        # The normal frontend transaction mounts only the UI and retains the
        # ledger's live shared backend. Its package sources were checked above.
        return []

    with scopes.replace(scope_release.scope_changes, check=check):
        return tool.prepare(candidate_root, 'frontend', 'shared')
