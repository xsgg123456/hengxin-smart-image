"""Admit only the reviewed log capture backend on each group's own baseline."""
import catalog
import scope_changes
import snapshot


BASE = {
    'domestic': '009a1808f5c4ebc2a496a407690151ef050039c0',
    'overseas': 'faab6d0434dcab1f42ef743d60d4fd32160fc714',
}
FRONTEND = {**BASE, 'overseas': '7b6caf1d98d6a4374bb782c681c4dacd8f5e39c3'}
SCHEMA = {'domestic': '0046', 'overseas': 'overseas_0029'}
BASE_INVENTORY = {
    'domestic': '42592904d0a1182bbf4acaa4c73c68b831f1c1dd1790cdb01d821777533ddd49',
    'overseas': '9b67ba01c05e300ac443042a500e6612fd9544ef2e1089b0ff5a9836b88a10e7',
}
CANDIDATE = {
    'domestic': '2d42d0d782429453f86ba31ba22f50e0a32c0d4d',
    'overseas': '476d7c610a303a79b84e9e88ac87a0b4773eb623',
}
CANDIDATE_INVENTORY = {
    'domestic': '23a7a489ade46b9d3bbbc234a604c2c5fc3b67f559b29807b0bade093755682b',
    'overseas': '7a80181b35cf031f9d9736165684e88c6138634d6c56f10f7686aa0bf02a3876',
}


def validate(data, selected, before, candidate, root, scope):
    if scope not in BASE or data.get('version') != 2 or str(root) not in catalog.check(data)['staged']:
        raise RuntimeError('CLI log maintenance requires a staged business candidate')
    if (selected['backend_commit'] != BASE[scope] or selected['frontend_commit'] != FRONTEND[scope]
            or selected['schema'] != {scope: SCHEMA[scope]}):
        raise RuntimeError('CLI log maintenance production baseline differs')
    snapshot.compatible(before, candidate, 'full')
    if not before.get('runtime_inputs') or before['runtime_inputs'] != candidate.get('runtime_inputs'):
        raise RuntimeError('CLI log maintenance cannot change runtime inputs')
    for manifest, commit, inventory in ((before, BASE[scope], BASE_INVENTORY[scope]),
                                        (candidate, CANDIDATE[scope], CANDIDATE_INVENTORY[scope])):
        provenance = manifest['provenance']
        files = scope_changes.backend_files(manifest)
        sources = {n: h for n, h in provenance['source_files'].items() if n.startswith('backend/')}
        if (manifest['commit'] != commit or provenance['source_commit'] != commit
                or manifest.get('scope') != scope
                or provenance['build']['environment'].get('VITE_RELEASE_SCOPE') != scope
                or sources != files or catalog.state_sha(files) != inventory):
            raise RuntimeError('CLI log maintenance source commit, scope or backend inventory differs')
