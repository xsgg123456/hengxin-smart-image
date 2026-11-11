"""Generate the isolated .245 deployment, offline; never start services or print secrets."""
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
from urllib.parse import quote, unquote, urlsplit, urlunsplit

ROOT = Path('/opt/hengxin-lan')
SOURCE = Path('/var/lib/hengxin-migration/lan-245/source-runtime.json')
PROJECTS = {'hengxin-vps-staging': 'domestic', 'hengxin-overseas': 'overseas',
            'hengxin-identity': 'identity'}
EXPECTED = {'domestic': 'api outbox api-image-outbox api-image-worker image-variants web postgres redis minio',
            'overseas': 'api skill-publisher overseas-postgres overseas-redis overseas-minio',
            'identity': 'identity-api identity-redis'}
SUBNET = '172.30.245.0/24'
GATEWAY = '172.30.245.1'
NGINX = '/opt/hengxin-smart-image/infra/nginx.vps.conf'
VOLATILE = {'INVOCATION_ID', 'JOURNAL_STREAM', 'SYSTEMD_EXEC_PID',
            'MEMORY_PRESSURE_WATCH', 'MEMORY_PRESSURE_WRITE', 'RUNTIME_DIRECTORY'}


def env_of(c):
    return dict(x.split('=', 1) for x in c['Config']['Env'])


def identity(c):
    labels = c['Config']['Labels']
    return PROJECTS[labels['com.docker.compose.project']], labels['com.docker.compose.service']


def escaped(value):
    if isinstance(value, str):
        return value.replace('$', '$$')
    if isinstance(value, list):
        return [escaped(x) for x in value]
    if isinstance(value, dict):
        return {k: escaped(v) for k, v in value.items()}
    return value


def endpoint(value, host, port, password=None):
    uri = urlsplit(value if '://' in value else '//' + value)
    auth = ''
    if password is not None:
        auth = quote(unquote(uri.username or ''), safe='') + ':' + quote(password, safe='') + '@'
    address = auth + host + ':' + str(port)
    return urlunsplit((uri.scheme, address, uri.path, uri.query, uri.fragment)).removeprefix('//')


def environment(original, scope, credentials, ports, native=False, aliases=()):
    env = {k: v for k, v in original.items() if k not in VOLATILE}
    own = credentials[scope]
    for key, value in list(env.items()):
        if key.endswith(('DATABASE_URL', 'REDIS_URL', 'BROKER_URL', 'MINIO_ENDPOINT', 'IDENTITY_SERVICE_URL')):
            uri = urlsplit(value if '://' in value else '//' + value)
            if uri.hostname == '127.0.0.1' and uri.port == 1:
                continue  # Publisher deliberately disables unused clients.
            kind = ('postgres' if key.endswith('DATABASE_URL') else 'redis' if key.endswith(('REDIS_URL', 'BROKER_URL'))
                    else 'minio' if key.endswith('MINIO_ENDPOINT') else 'identity-api')
            target = 'identity-api' if kind == 'identity-api' else scope + '-' + kind
            password = own.get(kind) if kind in ('postgres', 'redis') else None
            port = ports[target] if native else {'postgres': 5432, 'redis': 6379, 'minio': 9000, 'identity-api': 8000}[kind]
            env[key] = endpoint(value, '127.0.0.1' if native else target, port, password)
        elif key in ('POSTGRES_PASSWORD', 'REDIS_PASSWORD', 'MINIO_ROOT_PASSWORD'):
            env[key] = own[{'POSTGRES_PASSWORD': 'postgres', 'REDIS_PASSWORD': 'redis', 'MINIO_ROOT_PASSWORD': 'minio'}[key]]
        elif key.endswith('MINIO_SECRET_KEY'):
            env[key] = own['minio']
        elif key.endswith('MINIO_ACCESS_KEY') or key == 'MINIO_ROOT_USER':
            env[key] = own['minio_user']
        elif key in ('IDENTITY_SERVICE_KEY', 'OVERSEAS_IDENTITY_SERVICE_KEY'):
            env[key] = credentials['overseas' if key.startswith('OVERSEAS_') else 'domestic']['identity']
        elif key in ('IDENTITY_DOMESTIC_SERVICE_KEY', 'IDENTITY_OVERSEAS_SERVICE_KEY'):
            env[key] = credentials[key.split('_')[1].lower()]['identity']
        elif key.endswith('PUBLIC_ORIGIN'):
            env[key] = 'https://zhitu.qhhengxin.top'
    proxy = 'http://127.0.0.1:7890' if native else 'http://' + GATEWAY + ':7891'
    bypass = ','.join(sorted(set(aliases) | {'localhost', 'host.docker.internal', '127.0.0.1', '::1', '192.168.0.0/16',
                                           '10.0.0.0/8', '172.16.0.0/12', 'api.dingtalk.com', 'oapi.dingtalk.com'}))
    env.update({k: proxy for k in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy')})
    env.update(NO_PROXY=bypass, no_proxy=bypass)
    return env


def runtime_fields(c):
    cfg, host = c['Config'], c['HostConfig']
    if any(host.get(k) for k in ('Privileged', 'Devices', 'VolumesFrom', 'Links', 'PidMode', 'UsernsMode')):
        raise ValueError('unexpected host coupling')
    if host.get('NetworkMode') in ('host', 'none') or str(host.get('NetworkMode', '')).startswith('container:'):
        raise ValueError('unexpected network mode')
    result = {target: cfg.get(source) for source, target in
              [('Cmd', 'command'), ('Entrypoint', 'entrypoint'), ('User', 'user'), ('WorkingDir', 'working_dir')]}
    mapping = {'Memory': 'mem_limit', 'MemorySwap': 'memswap_limit', 'MemoryReservation': 'mem_reservation',
               'CpuShares': 'cpu_shares', 'CpuQuota': 'cpu_quota', 'CpuPeriod': 'cpu_period', 'CpusetCpus': 'cpuset',
               'PidsLimit': 'pids_limit', 'SecurityOpt': 'security_opt', 'GroupAdd': 'group_add', 'CapAdd': 'cap_add',
               'CapDrop': 'cap_drop', 'ReadonlyRootfs': 'read_only', 'ShmSize': 'shm_size', 'Init': 'init',
               'Sysctls': 'sysctls', 'Dns': 'dns', 'DnsOptions': 'dns_opt', 'DnsSearch': 'dns_search',
               'IpcMode': 'ipc', 'Runtime': 'runtime', 'OomScoreAdj': 'oom_score_adj', 'OomKillDisable': 'oom_kill_disable'}
    result.update({v: host[k] for k, v in mapping.items() if host.get(k)})
    if host.get('NanoCpus'):
        result['cpus'] = host['NanoCpus'] / 1e9
    if host.get('Ulimits'):
        result['ulimits'] = {x['Name']: {'soft': x['Soft'], 'hard': x['Hard']} for x in host['Ulimits']}
    if host.get('Tmpfs'):
        result['tmpfs'] = [k + ':' + v for k, v in host['Tmpfs'].items()]
    restart = host['RestartPolicy']
    result['restart'] = restart['Name'] or 'no'
    if restart['Name'] == 'on-failure' and restart['MaximumRetryCount']:
        result['restart'] += ':' + str(restart['MaximumRetryCount'])
    log = host.get('LogConfig')
    if log:
        result['logging'] = {'driver': log['Type'], 'options': log['Config']}
    if cfg.get('Healthcheck'):
        names = {'Test': 'test', 'Interval': 'interval', 'Timeout': 'timeout', 'Retries': 'retries',
                 'StartPeriod': 'start_period', 'StartInterval': 'start_interval'}
        result['healthcheck'] = {names[k]: str(v) + 'ns' if k not in ('Test', 'Retries') else v
                                 for k, v in cfg['Healthcheck'].items() if v}
    for source, target in [('StopSignal', 'stop_signal'), ('StopTimeout', 'stop_grace_period')]:
        if cfg.get(source):
            result[target] = str(cfg[source]) + ('s' if source == 'StopTimeout' else '')
    return result


def build(data):
    containers = data['containers']
    if {identity(c) for c in containers} != {(s, n) for s, names in EXPECTED.items() for n in names.split()} or len(containers) != 16:
        raise ValueError('unexpected service inventory')
    if any(not re.fullmatch(r'sha256:[a-f0-9]{64}', c['Image']) for c in containers):
        raise ValueError('immutable image IDs required')
    credentials = {s: {k: secrets.token_hex(24) for k in ('postgres', 'redis', 'minio', 'identity')}
                   | {'minio_user': 'lan_' + s + '_' + secrets.token_hex(6)} for s in EXPECTED}
    networks = sorted({n for c in containers for n in c['NetworkSettings']['Networks']})
    if 'hengxin-vps-staging_default' not in networks:
        raise ValueError('required proxy bridge missing')
    netmap = {n: 'network-' + str(i) for i, n in enumerate(networks)}
    compose = {'name': 'hengxin-lan', 'services': {}, 'networks': {}, 'volumes': {}}
    aliases, ports = set(), {}
    for c in containers:
        scope, name = identity(c)
        canonical = scope + '-' + name.removeprefix(scope + '-')
        aliases.add(canonical)
        for net in c['NetworkSettings']['Networks'].values():
            aliases.update(a for a in net.get('Aliases') or [] if not a.startswith('hengxin-'))
        for container_port, bindings in (c['HostConfig'].get('PortBindings') or {}).items():
            if bindings and container_port.split('/')[0] in ('5432', '6379', '9000', '8000'):
                ports[canonical] = int(bindings[0]['HostPort'])
    if not {'identity-api', 'domestic-postgres', 'domestic-redis', 'domestic-minio',
            'overseas-postgres', 'overseas-redis', 'overseas-minio'} <= ports.keys():
        raise ValueError('missing required published dependency')
    for old, new in netmap.items():
        compose['networks'][new] = {'name': 'hengxin-lan-' + new, 'driver': 'bridge'}
        if old == 'hengxin-vps-staging_default':
            compose['networks'][new]['ipam'] = {'config': [{'subnet': SUBNET, 'gateway': GATEWAY}]}
    report = {'services': [], 'native_units': [], 'network_mapping': netmap,
              'uid_mapping': {'codex': 1001, 'hengxin-overseas': 1002, 'auth_group': 986}}
    for c in containers:
        scope, name = identity(c)
        key = scope + '-' + name.removeprefix(scope + '-')
        service = runtime_fields(c)
        env = environment(env_of(c), scope, credentials, ports, aliases=aliases)
        service.update(image=c['Image'], pull_policy='never', container_name='hengxin-lan-' + key,
                       environment=env, networks={}, volumes=[], ports=[], extra_hosts=['host.docker.internal:' + GATEWAY])
        if name.endswith('redis'):
            env['REDIS_PASSWORD'] = credentials[scope]['redis']
            if scope == 'domestic':
                service['command'] = service['command'] + ['--requirepass', credentials[scope]['redis']]
                service['healthcheck']['test'] = ['CMD-SHELL', 'REDISCLI_AUTH="$REDIS_PASSWORD" redis-cli ping | grep -q PONG']
        for old, net in c['NetworkSettings']['Networks'].items():
            keep = {a for a in net.get('Aliases') or [] if a != c['Name'].lstrip('/') and not a.startswith('hengxin-')}
            if name == 'skill-publisher':
                keep.discard('overseas-api')
            service['networks'][netmap[old]] = {'aliases': sorted(keep | {key})}
        for mount in c['Mounts']:
            dest, source, kind = mount['Destination'], mount['Source'], mount['Type']
            if kind == 'volume' and dest in ('/var/lib/hengxin-overseas/execution', '/var/lib/hengxin-overseas/skills'):
                kind, source = 'bind', dest
            elif kind == 'volume':
                source = re.sub('[^a-zA-Z0-9_-]', '-', scope + '-' + mount['Name'])
                compose['volumes'][source] = {'name': 'hengxin-lan-' + source}
            elif kind != 'bind' or not source.startswith(('/opt/hengxin-', '/var/lib/hengxin-', '/run/hengxin-')) or '..' in Path(source).parts:
                raise ValueError('unexpected mount source')
            if source == NGINX:
                source = str(ROOT / 'nginx.conf')
            item = {'type': kind, 'source': source, 'target': dest, 'read_only': not mount['RW']}
            if kind == 'bind':
                item['bind'] = {'create_host_path': False, 'propagation': mount.get('Propagation') or 'rprivate'}
            service['volumes'].append(item)
        for port, bindings in (c['HostConfig'].get('PortBindings') or {}).items():
            target, protocol = port.split('/')
            service['ports'] += [{'target': int(target), 'published': b['HostPort'], 'host_ip': '127.0.0.1', 'protocol': protocol} for b in bindings or []]
        compose['services'][key] = service
        report['services'].append({'source': c['Name'], 'target': service['container_name'], 'image': c['Image'],
                                   'changed_environment_keys': sorted(k for k, v in env.items() if env_of(c).get(k) != v),
                                   'mounts': service['volumes'], 'networks': service['networks'], 'ports': service['ports']})
    native = {}
    for unit in data['units']:
        scope = 'overseas' if unit['name'].startswith('hengxin-overseas-') else 'domestic'
        native[unit['name']] = environment(unit['environment'], scope, credentials, ports, True, aliases)
        report['native_units'].append({'name': unit['name'], 'changed_environment_keys': sorted(k for k, v in native[unit['name']].items() if unit['environment'].get(k) != v)})
    nginx = data['config_files'][NGINX].replace('http://api:8000', 'http://domestic-api:8000')
    nginx = nginx.replace('X-Forwarded-Proto $scheme;', 'X-Forwarded-Proto $http_x_forwarded_proto;')
    report['changes'] = ['internal credentials rotated; external API credentials retained', 'new local volumes and networks; no external references',
                         'overseas execution/skills share host bind paths', 'publisher duplicate overseas-api alias removed',
                         'all published ports loopback; same HTTPS origin', 'domestic Redis authentication enabled',
                         'container proxy 172.30.245.1:7891; native proxy 127.0.0.1:7890', 'native systemd transient environment removed']
    return {'compose.json': escaped(compose), 'native-env.json': native, 'differences.json': report, 'nginx.conf': nginx}


def write_outputs(outputs, root=ROOT):
    root = Path(root)
    if set(outputs) != {'compose.json', 'native-env.json', 'differences.json', 'nginx.conf'}:
        raise ValueError('unexpected output inventory')
    if root != ROOT or root.resolve() != root:
        raise ValueError('target path mismatch')
    if any((root / name).exists() or (root / name).is_symlink() for name in outputs):
        raise FileExistsError('output already exists')
    if root.exists() and (root.stat().st_uid != os.getuid() or root.stat().st_mode & 0o022):
        raise ValueError('unsafe output directory')
    root.mkdir(mode=0o700, exist_ok=True)
    for name, value in outputs.items():
        fd = os.open(root / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as stream:
            stream.write(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2))


def main():
    if socket.gethostname() != 'hengxin-ai-245' or os.geteuid() != 0:
        raise RuntimeError('target host/root required')
    routes = json.loads(subprocess.check_output(['ip', '-j', 'route', 'show', 'table', 'all']))
    if any(ipaddress.ip_network(r['dst'], strict=False).overlaps(ipaddress.ip_network(SUBNET))
           for r in routes if r.get('dst') not in (None, 'default') and ':' not in r['dst']):
        raise RuntimeError('target subnet overlaps existing route')
    if SOURCE.is_symlink() or SOURCE.resolve() != SOURCE:
        raise RuntimeError('source path mismatch')
    outputs = build(json.loads(SOURCE.read_text()))
    write_outputs(outputs)
    print('Generated protected compose, native environment, nginx and non-secret differences; no services started.')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('Generation refused; inspect hostname, paths, inventory and network preconditions privately.')
