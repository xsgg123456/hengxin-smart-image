"""One-time semantic verification; never change the failed baseline or restart services."""
import argparse
import importlib.util
import json
import os
from pathlib import Path

import codex_auth_api_semantics as s
import codex_auth_runtime as r

spec = importlib.util.spec_from_file_location('auth_api', Path(__file__).with_name('codex-auth-api.py'))
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)


def verify(work):
    evidence_paths = [work / name for name in ('api-prepared.json', 'api-stage.json', 'api-patch.json',
                      'API_INSTALL_TESTS_PASSED', 'api-overlay.json')]
    before = {str(path): r.digest(path) for path in evidence_paths}
    data = json.loads((work / 'api-prepared.json').read_text())
    r.require(data['id'] == s.OLD_ID and data['old_image'] == s.OLD_IMAGE and data['image'] == s.NEW_IMAGE,
              'Recovery is restricted to the verified release identities')
    r.require(json.loads((work / 'api-stage.json').read_text()) == {'phase': 'started'}, 'Unexpected API recovery stage')
    r.require(api.package(work) == data['files'] and r.digest(work / 'api-patch.json') == data['manifest'], 'API manifest drift')
    r.require(json.loads((work / 'API_INSTALL_TESTS_PASSED').read_text()) ==
              {'manifest': data['manifest'], 'image': s.NEW_IMAGE}, 'Installed test receipt drift')
    r.require(all(r.digest(path) == digest for path, digest in data['config_files'].items()), 'Frozen configuration files drift')
    r.require(json.loads((work / 'api-overlay.json').read_text()) ==
              {'services': {'api': {'image': s.NEW_IMAGE}}}, 'API override drift')
    old_hash = api.compose(data, 'config', '--hash', 'api')
    r.require(old_hash == 'api ' + s.OLD_SERVICE_HASH, 'Frozen source service hash differs from pre-cutover observation')
    full = json.loads(api.compose(data, 'config', '--format', 'json'))
    new_hash = api.compose(data, 'config', '--hash', 'api', override=work / 'api-overlay.json')
    r.require(new_hash.startswith('api ') and len(new_hash.split()[1]) == 64, 'Invalid derived service hash')
    base = json.loads(r.run('docker', 'image', 'inspect', s.OLD_IMAGE))[0]['Config']
    live = api.inspect()
    r.require(live['Id'] == s.NEW_ID and live['Image'] == s.NEW_IMAGE and live['State']['Running'], 'Current API identity differs')
    r.require(live['State'].get('Health', {}).get('Status') == 'healthy', 'Current API is not healthy')
    s.verify_semantics(live, full, base, data, new_hash.split()[1], work)
    code = ('import hashlib,json,pathlib;print(json.dumps({p:hashlib.sha256(pathlib.Path("/app",p)'
            '.read_bytes()).hexdigest() for p in ' + repr(sorted(api.FILES)) + '}))')
    installed = json.loads(r.run('docker', 'exec', s.NEW_ID, 'python', '-B', '-c', code))
    r.require(installed == {name: entry['sha256'] for name, entry in data['files'].items()}, 'Actual API source differs')
    changed = r.run('docker', 'diff', s.NEW_ID).splitlines()
    r.require(not any(row[2:].startswith('/app/') and row.endswith('.py') for row in changed), 'Container Python source modified outside image')
    r.require(api.other_topology() == data['other'], 'Another container or native worker changed')
    r.run('curl', '--max-time', '10', '-fsS', '-o', '/dev/null',
          'http://127.0.0.1:18018/api/overseas/v1/health/ready', timeout=12)
    r.require(api.inspect()['Id'] == s.NEW_ID and api.other_topology() == data['other'], 'Topology changed during verification')
    r.require(all(r.digest(path) == digest for path, digest in before.items()), 'Original evidence changed during recovery')
    output = dict(status='verified-by-frozen-semantics', container=s.NEW_ID, image=s.NEW_IMAGE,
        oldContainer=s.OLD_ID, oldImage=s.OLD_IMAGE, manifest=data['manifest'],
        originalServiceHash=s.OLD_SERVICE_HASH, newServiceHash=new_hash.split()[1],
        originalConfigDigest=data['config'], observedConfigDigest=api.config_hash(live),
        checked=['full Config', 'full HostConfig', 'mounts', 'networks/aliases', 'installed source',
                 'image-bound install receipt', 'health', 'other containers and native workers'],
        originalEvidencePreserved=True, restartedServices=False,
        limitation='Original full inspect was not saved; exact differing raw hash field is unproven. '
                   'Frozen Compose and old image semantics match. This receipt does not replace the original digest.')
    r.private(work / 'API_RECOVERY_VERIFIED.json', output)
    print('API_RECOVERY_VERIFIED_FROZEN_SEMANTICS_NO_RESTART')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, default=r.WORK)
    args = parser.parse_args()
    r.require(os.geteuid() == 0, 'Root required for private deployment evidence')
    import fcntl
    with (args.work / '.deploy.lock').open('a') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        verify(args.work)


if __name__ == '__main__':
    main()
