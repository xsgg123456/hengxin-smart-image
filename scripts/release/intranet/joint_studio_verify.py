"""Read-only checks of live domestic Studio mounts, identities and permissions."""
import json
from pathlib import Path
import stat

import domestic_studio_wiring as wiring
import joint_studio_paths as paths
import joint_studio_gate_wiring as gate_wiring


def environment(info):
    values = info['Config'].get('Env') or []
    if any(not isinstance(row, str) or '=' not in row for row in values):
        raise RuntimeError('Invalid container environment')
    pairs = [row.split('=', 1) for row in values]
    if len({key for key, _ in pairs}) != len(pairs):
        raise RuntimeError('Duplicate container environment')
    return dict(pairs)


def mount(info, path, writable):
    found = [row for row in info['Mounts'] if row.get('Destination') == path]
    if (len(found) != 1 or found[0].get('Source') != path or found[0].get('Type') != 'bind'
            or found[0].get('RW') is not writable):
        raise RuntimeError('Domestic Studio mount differs: ' + path)


def host_directory(u, path, gid, mode):
    path = Path(path)
    u.safe(path.parent)
    info = path.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_gid != gid
            or stat.S_IMODE(info.st_mode) != mode):
        raise RuntimeError('Domestic Studio directory identity differs: ' + str(path))


def configuration(live, ctx):
    gate_wiring.verify(live, ctx)
    api, publisher = live['domestic-api'], live[wiring.PUBLISHER]
    api_env, publish_env = environment(api), environment(publisher)
    required = dict(wiring.native_environment(), DOMESTIC_SKILL_PUBLISH_SOCKET=wiring.SOCKET)
    if any(api_env.get(key) != value for key, value in required.items()):
        raise RuntimeError('Domestic API Studio environment differs')
    for name in ('hengxin-vps-codex-worker', 'hengxin-domestic-deletions'):
        if any(ctx[name]['env'].get(key) != value for key, value in wiring.native_environment().items()):
            raise RuntimeError('Domestic native Studio environment differs: ' + name)
    paths.identities(ctx)
    for path, writable in ((wiring.SKILLS, False), (wiring.LOCKS, True), (wiring.SOCKET_DIR, False)):
        mount(api, path, writable)
    for path in (wiring.SKILLS, wiring.TRANSFERS, wiring.SOCKET_DIR):
        mount(publisher, path, True)
    if (publish_env.get('DATABASE_URL') != api_env.get('DATABASE_URL')
            or publish_env.get('DOMESTIC_SKILL_ROOT') != wiring.SKILLS
            or publish_env.get('DOMESTIC_SKILL_TRANSFER_ROOT') != wiring.TRANSFERS
            or publish_env.get('DOMESTIC_SKILL_PUBLISH_SOCKET') != wiring.SOCKET
            or publish_env.get('DOMESTIC_STUDIO_PROTECTED') != '1'
            or any(key.startswith(('OVERSEAS_', 'DINGTALK_', 'IDENTITY_')) for key in publish_env)):
        raise RuntimeError('Domestic publisher environment differs')
    host = publisher['HostConfig']
    if (publisher['Config'].get('User') != '0:0' or host.get('Privileged')
            or not host.get('ReadonlyRootfs') or set(host.get('CapDrop') or []) != {'ALL'}
            or set(host.get('CapAdd') or []) not in ({'CHOWN'}, {'CAP_CHOWN'})
            or not ({'no-new-privileges:true', 'no-new-privileges=true'} & set(host.get('SecurityOpt') or []))
            or host.get('PortBindings') or host.get('NetworkMode') == 'host'):
        raise RuntimeError('Domestic publisher privileges differ')


def runtime(u, live, ctx):
    configuration(live, ctx)
    for path, gid, mode in ((paths.ROOT, 0, 0o755), (Path(wiring.SKILLS), 0, 0o755),
                            (Path(wiring.TRANSFERS), 0, 0o700), (Path(wiring.LOCKS), 986, 0o2770),
                            (Path(wiring.SOCKET_DIR), 10001, 0o750), (paths.RELEASE_GATE, 0, 0o755)):
        host_directory(u, path, gid, mode)
    for name in ('workers', 'ingress'):
        paths.gate_state(u, name)
    u.safe(paths.TMPFILES)
    if paths.TMPFILES.read_bytes() != paths.TMPFILES_CONTENT or stat.S_IMODE(paths.TMPFILES.stat().st_mode) != 0o644:
        raise RuntimeError('Domestic publisher boot configuration differs')
    code = ("import os,json; p=" + repr(wiring.LOCKS) + "; s=" + repr(wiring.SKILLS) + "; "
            "print(json.dumps({'uid':os.getuid(),'groups':os.getgroups()+[os.getgid()],"
            "'locks_w':os.access(p,os.W_OK),'skills_r':os.access(s,os.R_OK),"
            "'skills_w':os.access(s,os.W_OK)}))")
    result = json.loads(u.run(['docker', 'exec', 'hengxin-lan-domestic-api', 'python', '-B', '-c', code]))
    if (result['uid'] != 10001 or 986 not in result['groups'] or not result['locks_w']
            or not result['skills_r'] or result['skills_w']):
        raise RuntimeError('Domestic API filesystem permissions differ')
    for name in ('hengxin-vps-codex-worker', 'hengxin-domestic-deletions'):
        result = json.loads(u.native_run(ctx[name], code=code))
        if (result['uid'] != ctx[name]['user'] or 986 not in result['groups'] or not result['locks_w']
                or not result['skills_r'] or result['skills_w']):
            raise RuntimeError('Domestic native filesystem permissions differ: ' + name)
