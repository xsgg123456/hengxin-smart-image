"""Immutable candidate for the overseas 0028 -> 0029 workbench release."""
import scope_changes
import snapshot
from overseas_design_policy import digest
import overseas_creative_history as history

SOURCE, TARGET = 'overseas_0028', 'overseas_0029'
SCOPE, COMMAND = 'overseas', 'creative'
MARKER, RECEIPT = 'intranet-overseas-creative.json', 'creative-migration.json'
BASE = '133f16ae213b1c39f1a4c8b8556a2feb7fb28d49'
FRONTEND_BASE = BASE
CANDIDATE = 'faab6d0434dcab1f42ef743d60d4fd32160fc714'
SOURCE_SHA = '618fd8c99594a71688bd46992436844bf368214b85135d0b4ba68fb0728d5c0a'
FRONTEND_SHA = '7247984aff79613d13e4bb781758e8288430e544a115175cea0dfb05a2476239'
SHARED_ASSETS = 'c722535539d734fb89c89e2df76aa4c37ab1fd98efcc7ebb2e522a1cc545f4e8'
DELTA_SHA = '294d59b0b3d4fc711d91d9f65d0144b0c60609c920e0e9ccabce6a45330b39c3'
SQL_SHA = '78b04ea29df9834afd16fd3127a520771d2185c40a013ae902cf009d17bc507e'
MIGRATION = 'backend/migrations/overseas/versions/0029_creative_tools.py'


def validate(before, candidate):
    provenance = candidate.get('provenance', {})
    env = provenance.get('build', {}).get('environment', {})
    if (before.get('commit') != BASE or candidate.get('commit') != CANDIDATE
            or candidate.get('scope') != SCOPE or provenance.get('source_commit') != CANDIDATE
            or env.get('VITE_RELEASE_SCOPE') != SCOPE or env.get('VITE_VERSION') != CANDIDATE[:12]
            or digest(provenance.get('source_files')) != SOURCE_SHA):
        raise RuntimeError('Unexpected creative workbench source or baseline')
    frontend = candidate.get('frontend_current_files', {})
    if (digest(frontend) != FRONTEND_SHA
            or any(candidate['files'].get(n) != h for n, h in frontend.items())
            or not before.get('runtime_inputs') or before['runtime_inputs'] != candidate.get('runtime_inputs')):
        raise RuntimeError('Unexpected creative workbench frontend or runtime')
    old, new = map(scope_changes.backend_files, (before, candidate))
    delta = {n: [old.get(n), new.get(n)] for n in old.keys() | new.keys() if old.get(n) != new.get(n)}
    if (digest(delta) != DELTA_SHA or MIGRATION not in delta or MIGRATION in old
            or any(not n.startswith('backend/app/overseas/') for n in delta if n != MIGRATION)):
        raise RuntimeError('Unexpected overseas backend or migration delta')
    return sorted(delta)


def check(original, u, before_root, candidate_root, scope, mode, **kwargs):
    if scope != SCOPE or mode != 'full' or any(kwargs.values()):
        raise RuntimeError('Creative maintenance requires overseas full mode')
    before, candidate = (snapshot.manifest(u, root) for root in (before_root, candidate_root))
    changed = validate(before, candidate)
    for root, manifest in ((before_root, before), (candidate_root, candidate)):
        scope_changes.sources(root, manifest)
    return changed
