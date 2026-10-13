"""Resume only a verified, closed-intake failure before migration or executor shutdown."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys


def load(work):
    path = work / 'src/scripts/release/member-release-deploy.py'
    spec = importlib.util.spec_from_file_location('pinned_member_deploy', path)
    controller = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(controller)
    return controller


def check_baseline(m, work, data, edge):
    for name in ('MIGRATION_STARTED', 'EXECUTORS_STOPPED', 'drained-before-outbox-stop.json',
                 'drained-after-outbox-stop.json', 'verification.json'):
        assert not (work / name).exists(), 'Failure progressed beyond supported recovery'
    assert (work / 'deploy.exit').read_text().strip() == '1'
    assert m.EDGE.read_text() == m.closed_config(edge), 'Closed edge configuration changed'
    for group, expected in m.GROUPS.items():
        saved = data[group]
        api = m.container(group, expected['api'])
        for path, digest in saved['files'].items():
            assert m.digest(path) == digest, 'Compose/configuration changed'
        running = set(m.run('docker', 'ps', '-q', '--no-trunc', '--filter',
                           'label=com.docker.compose.project=' + saved['project'], capture=True).split())
        assert running == {identity for name, identity in saved['ids'].items() if name != api}
        config = json.loads((work / (group + '-compose.private.json')).read_text())
        for name, identity in saved['ids'].items():
            actual = m.live(name)
            assert actual['Id'] == identity and actual['Mounts'] == saved['mounts'][name]
            assert actual['State']['Running'] == (name != api)
            if name == api:
                assert actual['State']['Status'] == 'exited'
                assert actual['State']['ExitCode'] in (0, 143) and not actual['State']['OOMKilled']
                assert actual['Config']['Image'] == config['services'][expected['api']]['image']
                labels = actual['Config']['Labels']
                assert labels['com.docker.compose.project'] == saved['project']
                assert labels['com.docker.compose.project.config_files'].split(',') == saved['paths']
                assert labels['com.docker.compose.project.working_dir'] == saved['cwd']
                assert (labels.get('com.docker.compose.project.environment_file') or None) == saved['env']
    native_paths = set()
    for unit, directory in data['native'].items():
        assert m.run('systemctl', 'show', unit, '-p', 'WorkingDirectory', '--value', capture=True) == directory
        for key in ('FragmentPath', 'DropInPaths', 'EnvironmentFiles'):
            value = m.run('systemctl', 'show', unit, '-p', key, '--value', capture=True)
            native_paths.update(part for part in value.split() if part.startswith('/'))
        m.run('systemctl', 'is-active', unit)
    assert native_paths == set(data['nativeFiles']), 'Native configuration file set changed'
    for path, digest in data['nativeFiles'].items():
        assert m.digest(path) == digest, 'Native configuration changed'
    m.prepared_settings(work, data)


def resume(work, recovery_commit):
    d = load(work)
    m = d.m
    source, manifest, image = m.validate(work, work.name)
    identity = m.image_id(work, image)
    assert (work / 'PREPARED').read_text() == identity
    assert m.r.sql('SELECT version_num FROM alembic_version') == '0027'
    assert m.u.sql('SELECT version_num FROM overseas_alembic_version') == 'overseas_0013'
    data = json.loads((work / 'topology.json').read_text())
    edge = (work / 'edge-before.conf').read_text()
    assert hashlib.sha256(edge.encode()).hexdigest() == data['edgeHash']
    check_baseline(m, work, data, edge)
    targets = json.loads((work / 'native-targets.json').read_text())
    destination = d.BACKUPS / manifest['release']
    assert not destination.exists(), 'Backup already exists; investigate instead of replaying'
    m.assets_safe(source)
    d.verify.closed()  # Edge is already closed; no reload race here.
    try:
        d.cutover(work, source, manifest, identity, data, targets, destination)
        m.EDGE.write_text(edge)
        m.u.reload_edge()
        d.verify.public()
        for name in ('MEMBER_RELEASE.json', 'FRONTEND_RELEASE.json', 'OVERSEAS_RELEASE.json'):
            m.private(m.APP / name, manifest)
        m.private(work / 'verification.json', dict(release=manifest['release'], image=identity,
            migration='0028', overseasMigration='overseas_0014', backup=str(destination),
            sourceHashes=True, allThreeAPIs=True, skills=14, historicalCleanup=False,
            recoveryCommit=recovery_commit, recoveryScriptSha256=m.digest(__file__)))
        print('MEMBER_RELEASE_COMPLETE ' + manifest['release'], flush=True)
    except BaseException:
        try:
            m.close_edge(edge)
        finally:
            m.stop_apis(data, work)
        print('ALL_API_INTAKE_CLOSED_FORWARD_RECOVERY_REQUIRED', flush=True)
        raise


if __name__ == '__main__':
    os.umask(0o077)
    assert not sys.flags.optimize and os.geteuid() == 0
    release, recovery_commit = sys.argv[1:3]
    assert re.fullmatch(r'overseas-20261013-[0-9a-f]{7}', release)
    assert re.fullmatch(r'[0-9a-f]{40}', recovery_commit)
    resume(Path('/opt/hengxin-releases') / release, recovery_commit)
