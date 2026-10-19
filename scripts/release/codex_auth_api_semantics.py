"""Strict frozen-Compose semantics for the 2026-10-19 API recovery only."""
import copy

import codex_auth_runtime as r

OLD_SERVICE_HASH = '3cc130218fcc8f6444b1cac0e0b909abac9403d2f072fb34c3e38c8ba0ce0422'
OLD_ID = '28111e09a52c8475c428a99e4039bd5eb6a6a72e85d407a2ef002b2ae063c2a5'
NEW_ID = 'df94a491fb8426051eab1724900b4d3c774224ce16c49679823f50c11541c41e'
OLD_IMAGE = 'sha256:f9caa9f7af03bcaa3d94929699fb146b5016cd652e121f25fd8fc6cbd2702699'
NEW_IMAGE = 'sha256:24012e456da28a6a1e4b4c25d0875acdb05ed9a04a6ebe07bbeedec7987d15fe'
SERVICE_KEYS = {'build', 'command', 'depends_on', 'entrypoint', 'environment', 'healthcheck',
                'image', 'init', 'mem_limit', 'networks', 'ports', 'pull_policy', 'restart', 'volumes'}
NULL_HOST = ('BlkioDeviceReadBps BlkioDeviceReadIOps BlkioDeviceWriteBps BlkioDeviceWriteIOps '
    'BlkioWeightDevice CapAdd CapDrop DeviceCgroupRules DeviceRequests Devices Dns DnsOptions '
    'DnsSearch GroupAdd Links MemorySwappiness OomKillDisable PidsLimit SecurityOpt Ulimits VolumesFrom').split()
ZERO_HOST = ('BlkioWeight CpuCount CpuPercent CpuPeriod CpuQuota CpuRealtimePeriod CpuRealtimeRuntime '
    'CpuShares IOMaximumBandwidth IOMaximumIOps MemoryReservation NanoCpus OomScoreAdj').split()
EMPTY_HOST = ('Cgroup CgroupParent ContainerIDFile CpusetCpus CpusetMems Isolation PidMode '
              'UTSMode UsernsMode VolumeDriver').split()
FALSE_HOST = ('AutoRemove Privileged PublishAllPorts ReadonlyRootfs').split()
MASKED = ['/proc/acpi', '/proc/asound', '/proc/interrupts', '/proc/kcore', '/proc/keys',
          '/proc/latency_stats', '/proc/sched_debug', '/proc/scsi', '/proc/timer_list',
          '/proc/timer_stats', '/sys/devices/virtual/powercap', '/sys/firmware']
READONLY = ['/proc/bus', '/proc/fs', '/proc/irq', '/proc/sys', '/proc/sysrq-trigger']


def env_map(values):
    pairs = [value.split('=', 1) for value in values]
    r.require(all(len(pair) == 2 for pair in pairs), 'Malformed runtime environment')
    result = dict(pairs)
    r.require(len(result) == len(pairs), 'Duplicate runtime environment key')
    return result


def duration(value):
    for unit, scale in [('ns', 1), ('us', 1000), ('ms', 1000000), ('s', 1000000000), ('m', 60000000000)]:
        if str(value).endswith(unit):
            return int(float(str(value)[:-len(unit)]) * scale)
    raise RuntimeError('Unsupported frozen healthcheck duration')


def expected(full, base, data, new_hash, work):
    c = full['services']['api']
    r.require(set(c) == SERVICE_KEYS, 'Unsupported frozen service fields')
    r.require(c['pull_policy'] == 'never', 'Unexpected image pull policy')
    environment = env_map(base['Env'])
    environment.update({k: str(v) for k, v in c['environment'].items()})
    ports = {str(v['target']) + '/' + v['protocol']:
             [{'HostIp': v.get('host_ip', ''), 'HostPort': str(v['published'])}] for v in c['ports']}
    health = c['healthcheck']
    healthcheck = {'Test': health['test'], 'Interval': duration(health['interval']),
                  'Timeout': duration(health['timeout']), 'Retries': health['retries']}
    if 'start_period' in health:
        healthcheck['StartPeriod'] = duration(health['start_period'])
    labels = dict(base.get('Labels') or {})
    labels.update({'com.docker.compose.config-hash': new_hash, 'com.docker.compose.container-number': '1',
        'com.docker.compose.depends_on': '', 'com.docker.compose.image': NEW_IMAGE,
        'com.docker.compose.oneoff': 'False', 'com.docker.compose.project': 'hengxin-overseas',
        'com.docker.compose.project.config_files': ','.join(data['paths'] + [str(work / 'api-overlay.json')]),
        'com.docker.compose.project.environment_file': data['env'],
        'com.docker.compose.project.working_dir': str(__import__('pathlib').Path(data['paths'][0]).parent),
        'com.docker.compose.replace': 'api-1', 'com.docker.compose.service': 'api',
        'com.docker.compose.version': '5.1.4'})
    config = dict(Hostname=NEW_ID[:12], Domainname='', User=base['User'], AttachStdin=False,
        AttachStdout=True, AttachStderr=True, ExposedPorts={p: {} for p in ports}, Tty=False,
        OpenStdin=False, StdinOnce=False, Env=environment, Cmd=c['command'], Healthcheck=healthcheck,
        Image=NEW_IMAGE, Volumes=None, WorkingDir=base['WorkingDir'], Entrypoint=c['entrypoint'], Labels=labels)
    host = {**dict.fromkeys(NULL_HOST), **dict.fromkeys(ZERO_HOST, 0),
            **dict.fromkeys(EMPTY_HOST, ''), **dict.fromkeys(FALSE_HOST, False)}
    host.update(ConsoleSize=[0, 0], CgroupnsMode='private', ExtraHosts=[], Init=c['init'],
        IpcMode='private', LogConfig={'Type': 'json-file', 'Config': {}}, MaskedPaths=MASKED,
        Memory=int(c['mem_limit']), MemorySwap=2 * int(c['mem_limit']), NetworkMode='hx-identity-overseas',
        PortBindings=ports, ReadonlyPaths=READONLY, RestartPolicy={'Name': c['restart'], 'MaximumRetryCount': 0},
        Runtime='runc', ShmSize=67108864)
    binds, mount_specs, mounts = [], [], {}
    for value in c['volumes']:
        kind, target, writable = value['type'], value['target'], not value.get('read_only', False)
        source = value['source'] if kind == 'bind' else full['volumes'][value['source']]['name']
        mounts[target] = (kind, source, writable)
        if kind == 'volume':
            binds.append(source + ':' + target + (':rw' if writable else ':ro'))
        else:
            r.require(kind == 'bind' and value.get('bind') == {'create_host_path': False}, 'Unknown frozen bind mode')
            mount_specs.append(dict(Type='bind', Source=source, Target=target, ReadOnly=not writable, BindOptions={}))
    host.update(Binds=sorted(binds), Mounts=sorted(mount_specs, key=lambda v: v['Target']))
    networks = {full['networks'][name]['name']: {'hengxin-overseas-api-1', 'api', *v.get('aliases', [])}
                for name, v in c['networks'].items()}
    return config, host, mounts, networks


def verify_semantics(live, full, base, data, new_hash, work):
    config, host, mounts, networks = expected(full, base, data, new_hash, work)
    actual_config = copy.deepcopy(live['Config'])
    actual_config['Env'] = env_map(actual_config['Env'])
    r.require(actual_config == config, 'Frozen API Config semantics differ')
    actual_host = copy.deepcopy(live['HostConfig'])
    actual_host['Binds'] = sorted(actual_host['Binds'])
    actual_host['Mounts'] = sorted(actual_host['Mounts'], key=lambda v: v['Target'])
    r.require(actual_host == host, 'Frozen API HostConfig semantics differ')
    actual_mounts = {v['Destination']: (v['Type'], v['Source'] if v['Type'] == 'bind' else v['Name'], v['RW'])
                     for v in live['Mounts']}
    r.require(len(actual_mounts) == len(live['Mounts']) and actual_mounts == mounts, 'API mounted data differs')
    actual_networks = {name: set(v.get('Aliases') or []) for name, v in live['NetworkSettings']['Networks'].items()}
    r.require(actual_networks == networks, 'API networks or aliases differ')
