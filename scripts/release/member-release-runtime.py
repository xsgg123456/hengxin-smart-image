"""Pinned three-service topology and preparation; never restart production here."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil


def module(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


r = module('overseas-runtime')
u = module('overseas-update-runtime')
skills = module('overseas-skills-runtime')
run, private, APP, EDGE = r.run, r.private, r.APP, r.EDGE
UNITS = ('hengxin-vps-codex-worker', *u.UNITS)
GROUPS = {
    'domestic': dict(project='hengxin-vps-staging', api='api', services=list(r.SERVICES)),
    'overseas': dict(project='hengxin-overseas', api='api', services=['api']),
    'identity': dict(project='hengxin-identity', api='identity-api', services=['identity-api']),
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def live(name):
    result = json.loads(run('docker', 'inspect', name, capture=True))[0]
    # Docker may return the same mounts in a different order on each inspect.
    result['Mounts'] = sorted(result['Mounts'], key=lambda mount: mount['Destination'])
    return result


def container(group, service):
    return GROUPS[group]['project'] + '-' + service + '-1'


def compose(data, *args, overlay=None, capture=False):
    command = ['docker', 'compose', '-p', data['project'], '--project-directory', data['cwd']]
    if data['env']:
        command += ['--env-file', data['env']]
    for path in [*data['paths'], *([str(overlay)] if overlay else [])]:
        command += ['-f', path]
    return run(*command, *args, capture=capture, cwd=data['cwd'])


def topology():
    result = {}
    for group, expected in GROUPS.items():
        api = live(container(group, expected['api']))
        labels = api['Config']['Labels']
        assert labels['com.docker.compose.project'] == expected['project']
        assert labels['com.docker.compose.service'] == expected['api']
        paths = labels['com.docker.compose.project.config_files'].split(',')
        env = labels.get('com.docker.compose.project.environment_file') or None
        cwd = labels['com.docker.compose.project.working_dir']
        if group == 'domestic':
            assert env is None and cwd == str(APP / 'infra'), 'Domestic Compose environment changed'
        files = [*paths, *([env] if env else [])]
        if not env and (Path(cwd) / '.env').exists():
            files += [str(Path(cwd) / '.env')]
        assert all(Path(p).is_file() and p.startswith('/opt/') for p in files)
        ids = run('docker', 'ps', '-q', '--filter',
                  'label=com.docker.compose.project=' + expected['project'], capture=True).split()
        rows = [live(value) for value in ids]
        names = {row['Name'].lstrip('/'): row['Id'] for row in rows}
        assert all(container(group, s) in names for s in expected['services'])
        result[group] = dict(project=expected['project'], paths=paths, env=env, cwd=cwd,
            ids=names, files={p: digest(p) for p in files},
            mounts={row['Name'].lstrip('/'): row['Mounts'] for row in rows})
    result['native'] = {unit: run('systemctl', 'show', unit, '-p', 'WorkingDirectory',
                                '--value', capture=True) for unit in UNITS}
    native_files = set()
    for unit in UNITS:
        for key in ('FragmentPath', 'DropInPaths', 'EnvironmentFiles'):
            value = run('systemctl', 'show', unit, '-p', key, '--value', capture=True)
            native_files.update(part for part in value.split() if part.startswith('/'))
    result['nativeFiles'] = {path: digest(path) for path in sorted(native_files)}
    result['edgeHash'] = digest(EDGE)
    return result


def validate(work, release):
    source = work / 'src'
    manifest = json.loads((source / 'release.json').read_text())
    assert manifest['release'] == release and manifest['frontendVersion'] == '0.2.29'
    assert manifest['migration'] == '0028' and manifest['overseasMigration'] == 'overseas_0014'
    r.hashes(source, manifest)
    return source, manifest, 'hengxin-smart-image-backend:' + release


def image_id(work, image):
    identity = run('docker', 'image', 'inspect', '--format', '{{.Id}}', image, capture=True)
    assert (work / 'INSTALL_TEST_IMAGE_ID').read_text() == identity
    return identity


def assets_safe(source):
    for path in (source / 'frontend/dist').rglob('*'):
        if path.is_file() and path.name not in ('index.html', 'index.html.gz'):
            target = APP / 'frontend/dist' / path.relative_to(source / 'frontend/dist')
            assert not target.exists() or digest(target) == digest(path), 'Shared asset collision: ' + str(target)


def same_settings(before, after, changed):
    """The additive override may change image/build, nothing else, including mounts."""
    before, after = json.loads(json.dumps(before)), json.loads(json.dumps(after))
    for name in changed:
        for config in (before, after):
            for key in ('image', 'build'):
                config['services'][name].pop(key, None)
    assert before == after, 'Compose changed settings other than image/build'


def check_live_config(group, config):
    for service in GROUPS[group]['services']:
        actual, declared = live(container(group, service)), config['services'][service]
        assert actual['State']['Running']
        assert actual['Config']['Image'] == declared['image'], 'Live image differs from Compose'
        env = dict(item.split('=', 1) for item in actual['Config']['Env'])
        assert all(env.get(k) == str(v) for k, v in declared.get('environment', {}).items()), service
        if declared.get('command'):
            assert actual['Config']['Cmd'] == declared['command'], service
        mounts = {row['Destination']: row for row in actual['Mounts']}
        assert len(mounts) == len(declared.get('volumes', [])), 'Undeclared live mounts'
        for volume in declared.get('volumes', []):
            mounted = mounts[volume['target']]
            assert mounted['RW'] == (not volume.get('read_only', False))
            if volume['type'] == 'bind':
                assert mounted['Source'] == volume['source']
            else:
                assert volume['type'] == 'volume'
                assert mounted['Name'] == config['volumes'][volume['source']]['name']


def prepared_settings(work, data):
    for group, expected in GROUPS.items():
        before = json.loads((work / (group + '-compose.private.json')).read_text())
        after = json.loads(compose(data[group], 'config', '--format', 'json',
                          overlay=work / (group + '-overlay.json'), capture=True))
        names = expected['services'] + ([] if group == 'identity' else ['migrate'])
        same_settings(before, after, names)


def prepare_domestic_native(source, release, old):
    old = Path(old)
    for name in ('pyproject.toml', 'uv.lock'):
        assert (source / 'backend' / name).read_bytes() == (old / name).read_bytes(), 'Native dependency drift'
    target = Path('/opt/hengxin-native-releases') / release / 'backend'
    assert not target.exists()
    target.parent.mkdir(parents=True, mode=0o755)
    target.parent.parent.chmod(0o755)
    shutil.copytree(source / 'backend', target)
    for path in (target.parent, target, *target.rglob('*')):
        path.chmod(0o755 if path.is_dir() else 0o644)
    (target / '.venv').symlink_to(old / '.venv', target_is_directory=True)
    run('runuser', '-u', 'codex', '--', str(target / '.venv/bin/python'), '-c',
        'import app,celery; print("DOMESTIC_NATIVE_IMPORT_PASS")', cwd=target)
    return target


def prepare(work, source, manifest, image):
    assert not (work / 'PREPARED').exists()
    identity = image_id(work, image)
    assert r.sql('SELECT version_num FROM alembic_version') == '0027'
    assert u.sql('SELECT version_num FROM overseas_alembic_version') == 'overseas_0013'
    assert json.loads((APP / 'frontend/package.json').read_text())['version'] == '0.2.28'
    assets_safe(source)
    data = topology()
    probe = module('member-release-drain')
    evidence = probe.evidence(work)
    probe.idle(evidence['workers'])  # Validate replies; busy is reported, not a prepare failure.
    private(work / 'prepare-queues.json', evidence)
    private(work / 'topology.json', data)
    for group, expected in GROUPS.items():
        old = json.loads(compose(data[group], 'config', '--format', 'json', capture=True))
        check_live_config(group, old)
        names = expected['services'] + ([] if group == 'identity' else ['migrate'])
        overlay = work / (group + '-overlay.json')
        private(overlay, {'services': {name: {'image': identity, 'build': {
            'context': str(source), 'dockerfile': 'infra/Dockerfile.backend'}} for name in names}})
        new = json.loads(compose(data[group], 'config', '--format', 'json', overlay=overlay, capture=True))
        same_settings(old, new, names)
        private(work / (group + '-compose.private.json'), old)
    targets = dict(domestic=str(prepare_domestic_native(source, manifest['release'], data['native'][UNITS[0]])),
                   overseas=str(u.prepare_native(source, manifest['release'])))
    assert data['native'][UNITS[1]] == data['native'][UNITS[2]]
    skills.verify(u, work, Path(targets['overseas']))
    private(work / 'native-targets.json', targets)
    assert topology() == data, 'Production topology drifted during preparation'
    private(work / 'PREPARED', identity)


def closed_config(original):
    for service in ('identity', 'overseas'):
        pattern = r'location \^~ /api/' + service + r'/v1/ \{[^{}]*\}'
        original, count = re.subn(pattern, 'location ^~ /api/' + service + '/v1/ { return 503; }', original)
        assert count == 1, 'Edge API block not unique'
    pattern = r'location \^~ /api/v1/ \{[^{}]*\}'
    if re.search(pattern, original):
        original, count = re.subn(pattern, 'location ^~ /api/v1/ { return 503; }', original)
        assert count == 1
    else:
        anchor = '    ssl_prefer_server_ciphers off;\n'
        assert original.count(anchor) == 1
        original = original.replace(anchor, anchor + '\n    location ^~ /api/v1/ { return 503; }\n')
    return original


def close_edge(original):
    EDGE.write_text(closed_config(original))
    u.reload_edge()


def stop_apis(data, work=None):
    errors = []
    for group, expected in GROUPS.items():
        try:
            compose(data[group], 'stop', '-t', '30', expected['api'],
                    overlay=work / (group + '-overlay.json') if work else None)
        except BaseException as exc:
            errors.append(exc)
    if errors:
        raise RuntimeError('One or more API intake stops failed') from errors[0]
