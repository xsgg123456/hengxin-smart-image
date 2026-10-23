"""Reviewed API-only grant patch. CLI: WORK prepare|deploy; private binding stays outside source."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import UUID

API = 'hengxin-overseas-api-1'
PG = 'hengxin-overseas-overseas-postgres-1'
KEY = 'OVERSEAS_FULL_ACCESS_MEMBER_IDS'
FILES = ['app/overseas/config.py', 'app/overseas/permissions.py',
         'app/overseas/auth/router.py', 'app/overseas/management/skills.py']


def run(args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=600, **kwargs).stdout.strip()


def private(path, value):
    with path.open('w', encoding='utf-8') as handle:
        os.chmod(path, 0o600)
        handle.write(json.dumps(value, ensure_ascii=False, indent=2))


def live():
    return json.loads(run(['docker', 'inspect', API]))[0]


def command(before, overlay=None):
    labels = before['Config']['Labels']
    assert labels['com.docker.compose.project'] == 'hengxin-overseas'
    paths = labels['com.docker.compose.project.config_files'].split(',')
    env = labels['com.docker.compose.project.environment_file']
    assert all(Path(p).is_file() and p.startswith('/opt/') for p in [*paths, env])
    result = ['docker', 'compose', '--env-file', env]
    for p in paths + ([str(overlay)] if overlay else []):
        result += ['-f', p]
    return result


def probe(work, verify=False, audit=False):
    binding = json.loads((work / 'binding.private.json').read_text())
    assert all(str(UUID(binding[k])) == binding[k] for k in ('actor', 'target'))
    code = (work / 'overseas-member-grant-probe.py').read_text()
    return json.loads(run(['docker', 'exec', '-i', API, 'python', '-',
                          binding['actor'], binding['target'], str(int(verify)), str(int(audit))], input=code))


def snapshot_others():
    return {r['Name']: (r['Id'], r['Image'], r['State']['StartedAt']) for r in
            json.loads(run(['docker', 'inspect', *run(['docker', 'ps', '-q']).split()]))
            if r['Name'] != '/' + API}


def prepare(work):
    assert not (work / 'prepared.private.json').exists(), 'Already prepared'
    before = live()
    assert before['State']['Health']['Status'] == 'healthy'
    assert before['Config']['WorkingDir'] == '/app'
    assert not any(m['Destination'].startswith('/app') for m in before['Mounts'])
    manifest = json.loads((work / 'manifest.json').read_text())
    assert set(manifest['files']) == set(FILES + ['tests/test_overseas_full_access_grant.py'])
    for name, hashes in manifest['files'].items():
        assert hashlib.sha256((work / 'src' / name).read_bytes()).hexdigest() == hashes['new']
        if name in FILES:
            remote = run(['docker', 'exec', API, 'sha256sum', '/app/' + name]).split()[0]
            assert remote == hashes['old'], 'Live source drift: ' + name
    initial = probe(work)
    assert initial['targetRole'] == ['design_manager'] and initial['actorRole'] == ['super_admin']
    assert not initial['equal'] and initial['actorToggle'] and not initial['targetToggle']
    assert initial['activeJobs'] == 0, 'Wait for overseas jobs to finish; do not interrupt'
    assert not initial['paused'], 'Admission was already paused'
    config = json.loads(run(command(before) + ['config', '--format', 'json']))
    assert not config['services']['api'].get('environment', {}).get(KEY), 'Existing grants require explicit merge'
    binding = json.loads((work / 'binding.private.json').read_text())
    tag = 'hengxin-overseas-member-grant:' + manifest['patch'][:16]
    base_tag = tag + '-base'
    run(['docker', 'tag', before['Image'], base_tag])
    assert run(['docker', 'image', 'inspect', '--format', '{{.Id}}', base_tag]) == before['Image']
    dockerfile = 'FROM ' + base_tag + '\n'
    for name in FILES:
        dockerfile += f'COPY --chmod=0644 src/{name} /app/{name}\n'
    dockerfile += 'COPY --chmod=0644 src/tests/test_overseas_full_access_grant.py /app/tests/test_overseas_full_access_grant.py\n'
    (work / 'Dockerfile').write_text(dockerfile)
    (work / '.dockerignore').write_text('*\n!Dockerfile\n!src\n!src/**\n')
    private(work / 'build-log.private.json', {'output': run(['docker', 'build', '--network=none', '-t', tag, str(work)])})
    # No production env, volumes or network are available to isolated installed-image tests.
    tests = run(['docker', 'run', '--rm', '--network=none', '--entrypoint', 'python', tag,
                 '-m', 'pytest', '-q', 'tests/test_overseas_full_access_grant.py',
                 'tests/test_overseas_permissions.py', 'tests/test_overseas_single_role.py',
                 'tests/test_overseas_skill_availability.py', 'tests/test_overseas_members.py',
                 'tests/test_overseas_configuration.py'])
    private(work / 'installed-tests.private.json', {'output': tests})
    image = run(['docker', 'image', 'inspect', '--format', '{{.Id}}', tag])
    overlay = {'services': {'api': {'image': image, 'environment': {KEY: json.dumps([binding['target']])}}}}
    private(work / 'grant-overlay.json', overlay)
    proposed = json.loads(run(command(before, work / 'grant-overlay.json') + ['config', '--format', 'json']))
    normalized = copy.deepcopy(proposed)
    normalized['services']['api']['image'] = config['services']['api']['image']
    normalized['services']['api']['environment'].pop(KEY)
    assert normalized == config, 'Unexpected Compose settings change'
    private(work / 'before.private.json', before)
    private(work / 'prepared.private.json', {'beforeId': before['Id'], 'image': image,
            'initial': initial, 'others': snapshot_others(), 'patch': manifest['patch']})
    print(json.dumps({'prepared': True, 'image': image, 'installedTests': tests.splitlines()[-1]}))


def deploy(work):
    assert not (work / 'DEPLOY_STARTED').exists(), 'Inspect previous attempt before retry'
    data = json.loads((work / 'prepared.private.json').read_text())
    before = json.loads((work / 'before.private.json').read_text())
    assert live()['Id'] == data['beforeId']
    assert probe(work) == data['initial'], 'Member or job state drift since prepare'
    # API replacement does not restart executors; admission is paused for the cutover.
    pause = 'import app.overseas.main\nfrom app.db.session import session_factory\nfrom app.overseas.execution.queue import lock_gate\nwith session_factory().begin() as s:\n lock_gate(s).paused = True\n'
    # The pause transaction locks the gate; the subsequent probe reads committed state.
    run(['docker', 'exec', '-i', API, 'python', '-'], input=pause)
    try:
        current = probe(work)
        assert current['activeJobs'] == 0, 'Overseas work arrived; leave paused for inspection'
        dump = work / 'overseas-before.dump'
        with dump.open('wb') as handle:
            os.chmod(dump, 0o600)
            subprocess.run(['docker', 'exec', PG, 'pg_dump', '-U', 'postgres', '-d', 'hengxin_overseas', '-Fc'], stdout=handle, stderr=subprocess.PIPE, check=True, timeout=300)
        assert dump.stat().st_size > 1000
        # Validate the archive directory without restoring or modifying production data.
        subprocess.run(['docker', 'exec', '-i', PG, 'pg_restore', '--list'], input=dump.read_bytes(), capture_output=True, check=True, timeout=60)
        (work / 'DEPLOY_STARTED').write_text(data['patch'])
        run(command(before, work / 'grant-overlay.json') + ['up', '-d', '--no-deps', '--no-build', '--pull', 'never', 'api'])
        end = time.monotonic() + 90
        while time.monotonic() < end:
            after = live()
            if after['State'].get('Health', {}).get('Status') == 'healthy':
                break
            time.sleep(2)
        else:
            raise RuntimeError('API did not become healthy; keep admission paused')
        assert after['Image'] == data['image']
        verified = probe(work, verify=True, audit=True)
        for key in ('members', 'skills', 'taskCount', 'migration'):
            assert verified[key] == data['initial'][key], 'Protected state changed: ' + key
        assert snapshot_others() == {k: tuple(v) for k, v in data['others'].items()}, 'Unrelated runtime changed'
        resume = pause.replace('= True', '= False')
        run(['docker', 'exec', '-i', API, 'python', '-'], input=resume)
        private(work / 'VERIFIED.json', verified)
        print(json.dumps({'verified': True, **verified}))
    except Exception:
        (work / 'ATTENTION_REQUIRED').write_text('Admission remains paused. Inspect before any further action; do not blindly rerun.')
        raise


if __name__ == '__main__':
    work = Path(sys.argv[1]).resolve(strict=True)
    assert str(work).startswith('/opt/hengxin-releases/member-grant-')
    assert work.stat().st_uid == 0 and work.stat().st_mode & 0o077 == 0
    assert sys.argv[2] in ('prepare', 'deploy')
    {'prepare': prepare, 'deploy': deploy}[sys.argv[2]](work)
