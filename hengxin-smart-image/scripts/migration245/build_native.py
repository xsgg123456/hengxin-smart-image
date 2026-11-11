"""Prepare isolated native units and one hash-guarded deployment patch; never start services."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import socket
import stat

DEPLOY_ROOT = '/etc/hengxin-lan'
ROOT = Path(DEPLOY_ROOT)
SYSTEMD = Path('/etc/systemd/system')
SOURCE = Path('/var/lib/hengxin-migration/lan-245/source-runtime.json')
ENV_SOURCE = Path('/opt/hengxin-lan/native-env.json')
ACCOUNT = Path('/opt/hengxin-account-releases/account-management-20261026-ce4baf4/daemon/app/account_management/service.py')
OLD_CALL = "BusinessBroker(args.runtime / 'worker.sock', managers)"
NEW_CALL = "BusinessBroker(args.runtime / 'worker.sock', managers, overseas_uid=int(os.environ.get('HX_OVERSEAS_WORKER_UID', '999')))"
UNITS = {'hengxin-codex-accounts', 'hengxin-codex-auth', 'hengxin-domestic-deletions',
         'hengxin-retention', 'hengxin-vps-codex-worker', 'hengxin-overseas-worker', 'hengxin-overseas-outbox'}
REPLACED = {'Environment', 'EnvironmentFile', 'WorkingDirectory', 'ExecStart'}
CODE_ROOTS = {'/opt/hengxin-account-releases/account-management-20261026-ce4baf4/daemon',
              '/opt/hengxin-native-releases/domestic-codex-auth-20261019/backend',
              '/opt/hengxin-native-releases/domestic-record-filters-20261022-2f08f8f/backend',
              '/opt/hengxin-overseas-releases/overseas-20261024-b6289eb/backend'}


def digest(content):
    return hashlib.sha256(content).hexdigest()


def unit_quote(value, executable=False):
    if not isinstance(value, str) or '\0' in value:
        raise ValueError('invalid unit string')
    value = value.replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%')
    value = value.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
    return '"' + (value.replace('$', '$$') if executable else value) + '"'


def unit_path(value):
    # These systemd directives parse paths directly, not ExecStart-style quoted words.
    if (not isinstance(value, str) or not value.startswith('/') or value.startswith('//')
            or str(PurePosixPath(value)) != value or '..' in PurePosixPath(value).parts
            or any(c.isspace() or ord(c) < 32 or ord(c) == 127 or c in '\\"\'' for c in value)):
        raise ValueError('unsafe unit path')
    return value.replace('%', '%%')


def env_text(env):
    rows = []
    for key, value in sorted(env.items()):
        if not re.fullmatch('[A-Za-z_][A-Za-z0-9_]*', key) or not isinstance(value, str) or '\0' in value:
            raise ValueError('invalid environment')
        # EnvironmentFile uses POSIX double-quote escapes, without variable/specifier expansion.
        value = re.sub(r'([\\"$`])', r'\\\1', value)
        rows.append(key + '="' + value + '"\n')
    return ''.join(rows)


def logical_lines(text):
    pending = ''
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith(('#', ';')) or not line:
            continue
        pending += line
        if pending.endswith('\\'):
            pending = pending[:-1] + ' '
            continue
        yield pending
        pending = ''
    if pending:
        raise ValueError('unfinished unit continuation')


def preserved(text):
    result, section = [], None
    for line in logical_lines(text):
        if line.startswith('[') and line.endswith(']'):
            section = line[1:-1]
            if section not in ('Unit', 'Service', 'Install'):
                raise ValueError('unexpected unit section')
            result.append(line)
            continue
        if section is None or '=' not in line:
            raise ValueError('invalid unit syntax')
        key, value = line.split('=', 1)
        key = key.strip()
        if section == 'Service' and key in REPLACED:
            continue
        if section == 'Service' and (key.startswith('Exec') or key in ('PassEnvironment', 'UnsetEnvironment')):
            raise ValueError('unexpected command/environment directive')
        result.append(key + '=' + value.strip())
    return result


def adapted(unit, environment):
    argv, env = list(unit['argv']), dict(environment)
    if not argv or not argv[0].startswith(('/usr/bin/python', unit['cwd'] + '/.venv/bin/')):
        raise ValueError('unexpected native executable')
    for index, value in enumerate(argv):
        if value.startswith('--hostname='):
            if '@' not in value:
                raise ValueError('unexpected worker hostname')
            argv[index] = value.rsplit('@', 1)[0] + '@hengxin-ai-245'
        if index and argv[index - 1] == '--allowed-uid' and value == '999':
            argv[index] = '1002'
    if unit['name'] == 'hengxin-codex-auth':
        allowed = [argv[i + 1] for i, item in enumerate(argv[:-1]) if item == '--allowed-uid']
        if sorted(allowed) != ['1001', '1002']:
            raise ValueError('unexpected broker UID authorization')
    if unit['name'] == 'hengxin-codex-accounts':
        if env.get('HX_OVERSEAS_WORKER_UID', '1002') != '1002':
            raise ValueError('incorrect account broker UID')
        env['HX_OVERSEAS_WORKER_UID'] = '1002'
    for key, value in env.items():
        if key.endswith('WORKER_NODE_NAME'):
            env[key] = value.replace('racknerd-058889d', 'hengxin-ai-245')
    return argv, env


def build(data, native):
    if {u['name'] for u in data['units']} != UNITS or len(data['units']) != 7 or set(native) != UNITS:
        raise ValueError('unexpected native inventory')
    outputs, manifest = {}, {'units': [], 'overseas_uid': 1002}
    for unit in data['units']:
        name, props = unit['name'], unit['properties']
        if unit['cwd'] not in CODE_ROOTS:
            raise ValueError('unexpected source code root')
        paths = [props['FragmentPath']] + props['DropInPaths'].split()
        expected = '/etc/systemd/system/' + name + '.service'
        if paths[0] != expected or any(not p.startswith(expected + '.d/') or '..' in Path(p).parts for p in paths[1:]):
            raise ValueError('unexpected unit source path')
        lines = []
        for path in paths:
            lines.extend(preserved(data['config_files'][path]))
        argv, env = adapted(unit, native[name])
        deps = 'network-online.target docker.service mihomo.service'
        if name in ('hengxin-vps-codex-worker', 'hengxin-overseas-worker'):
            deps += ' hengxin-codex-accounts.service'
        lines += ['[Unit]', 'After=' + deps, 'Wants=network-online.target', '[Service]',
                  'WorkingDirectory=' + unit_path(unit['cwd']),
                  'EnvironmentFile=' + unit_path(DEPLOY_ROOT + '/' + name + '.env'),
                  'ExecStart=' + ' '.join(unit_quote(arg, True) for arg in argv)]
        outputs[name + '.service'] = ('\n'.join(lines) + '\n').encode()
        outputs[name + '.env'] = env_text(env).encode()
        manifest['units'].append({'name': name, 'cwd': unit['cwd'], 'source_fragments': paths,
                                  'environment_keys': sorted(env), 'unit_sha256': digest(outputs[name + '.service'])})
    return outputs, manifest


def patch_plan(data, content):
    expected = data['native_hashes'][str(ACCOUNT)]['sha256']
    if digest(content) != expected:
        raise ValueError('account source hash drift')
    text = content.decode('utf-8')
    if text.count(OLD_CALL) != 1 or '\nimport os\n' not in text:
        raise ValueError('account patch anchor drift')
    patched = text.replace(OLD_CALL, NEW_CALL).encode()
    compile(patched, str(ACCOUNT), 'exec')
    return patched, {'path': str(ACCOUNT), 'source_sha256': expected, 'target_sha256': digest(patched),
                     'change': 'BusinessBroker overseas UID reads HX_OVERSEAS_WORKER_UID, default remains 999'}


def safe_path(path):
    path = Path(path)
    if not path.is_absolute() or path.resolve() != path:
        raise ValueError('unsafe path or symlink')
    for parent in (path, *path.parents):
        if parent.exists() and parent.is_symlink():
            raise ValueError('symlink refused')
    return path


def exclusive(path, content):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def install_candidate(data, native):
    safe_path(ROOT)
    safe_path(SYSTEMD)
    safe_path(ACCOUNT)
    if ROOT.exists():
        raise FileExistsError('candidate directory already exists')
    for name in UNITS:
        for target in (SYSTEMD / (name + '.service'), SYSTEMD / (name + '.service.d')):
            if target.exists() or target.is_symlink():
                raise FileExistsError('existing systemd definition refused')
    original = ACCOUNT.read_bytes()
    original_stat = ACCOUNT.stat()
    patched, delta = patch_plan(data, original)
    outputs, manifest = build(data, native)
    manifest['deployment_patch'] = delta
    outputs['manifest.json'] = json.dumps(manifest, ensure_ascii=False, indent=2).encode()
    outputs['account-service.source.py'] = original
    outputs['account-service.patched.py'] = patched
    if ROOT.parent.stat().st_dev != original_stat.st_dev:
        raise ValueError('atomic patch requires same filesystem')
    ROOT.mkdir(mode=0o700)
    for filename, content in outputs.items():
        exclusive(ROOT / filename, content)
    # Recheck both content and inode immediately before the authorized atomic replacement.
    safe_path(ACCOUNT)
    if ACCOUNT.stat().st_ino != original_stat.st_ino or ACCOUNT.read_bytes() != original:
        raise ValueError('source changed during preparation; candidates retained')
    temporary = ROOT / 'account-service.install.py'
    exclusive(temporary, patched)
    os.chmod(temporary, stat.S_IMODE(original_stat.st_mode))
    if hasattr(os, 'chown'):
        os.chown(temporary, original_stat.st_uid, original_stat.st_gid)
    os.replace(temporary, ACCOUNT)
    if digest(ACCOUNT.read_bytes()) != delta['target_sha256']:
        raise RuntimeError('deployment patch verification failed')


def main():
    if socket.gethostname() != 'hengxin-ai-245' or os.geteuid() != 0:
        raise RuntimeError('target host/root required')
    import pwd
    import grp
    if pwd.getpwnam('codex').pw_uid != 1001 or pwd.getpwnam('hengxin-overseas').pw_uid != 1002 or grp.getgrnam('hengxin-codex-auth').gr_gid != 986:
        raise RuntimeError('target UID/group mismatch')
    for path in (SOURCE, ENV_SOURCE):
        safe_path(path)
        if path.stat().st_uid != 0 or path.stat().st_mode & 0o077:
            raise ValueError('private input ownership/mode required')
    install_candidate(json.loads(SOURCE.read_text()), json.loads(ENV_SOURCE.read_text()))
    print('Prepared seven protected native unit candidates and verified deployment UID patch; no services started.')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('Native preparation refused; inspect target identity, private inputs, paths and source hashes privately.')
