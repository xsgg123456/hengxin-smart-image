"""Reviewed model-only delta against each business's own production backend."""

BASE = {
    'domestic': '02ddb53749a9e16580a965b64ea13ffdd19aef51',
    'overseas': '3b38a2c445149d4a0d12c4145cc90f9e173ab4aa',
}

CHANGES = {
    'backend/app/modules/api_image_edits/execution_policy.py': (
        'eea12fb565e2ecb8a23df9a8a66f8505a82299d060717be0598c12358bdbe338',
        '6f63bc70709e942453b8da10a26069f4d851708dd7ab3ff6c0420708e33bdbbc'),
    'backend/app/overseas/execution/runner.py': (
        'b94c5974ae0fa1c879de45150d60d12335a594b11eb808b95677aefa9eb02b7f',
        '1d470c5d40f9266e70726aaf45c5a6e61aa608a7919d0404807598fe0c5ab27c'),
    'backend/app/overseas/studio/execution.py': (
        '33a9cc7570a5b762fa9ee76720f6e6f0e0cc02aa3046b93b01175592f47b9a78',
        'f4cfb714f5faff68d454d80e98b29553b3835a26896a4b0664cef35d1fd7ce7a'),
}


def validate(before, candidate, scope, changed):
    if (scope not in BASE or before.get('commit') != BASE[scope]
            or candidate.get('scope') != scope):
        raise RuntimeError('Model maintenance requires the reviewed scope and production baseline')
    commit = candidate['commit']
    if commit == before['commit'] or candidate.get('provenance', {}).get('source_commit') != commit:
        raise RuntimeError('Model maintenance requires a new package with matching Git provenance')
    delta = {n: (before['files'].get(n), candidate['files'].get(n)) for n in changed}
    if delta != CHANGES:
        raise RuntimeError('Model maintenance requires exactly the reviewed backend file hashes')
