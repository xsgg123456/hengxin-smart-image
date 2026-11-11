"""One-time, pinned 1Panel installation on the authorized LAN host only."""
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import stat
import subprocess
import tarfile

BASE = Path('/opt/hengxin-monitor')
STAGE = Path('/var/lib/hengxin-panel-install/20261111')
PACKAGE = '1panel-v2.5.0-linux-amd64.tar.gz'
SHA = '106d088fc3b1e9caf8adce0b5c04d77d22af740045caedf5ac694d375f58d73c'
INSTALLER_SHA = '3faa744fd158283470b48b3a971dc98cc390c7f291d4287b170416ae862dd28f'
UNIT = 'hengxin-panel-access.service'
RULES = '''table inet hengxin_panel {
 chain input {
  type filter hook input priority -10; policy accept;
  iifname "lo" tcp dport 10086 accept
  ip saddr { 192.168.1.0/24, 192.168.2.0/23 } tcp dport 10086 accept
  tcp dport 10086 counter drop
 }
}
'''
ACCESS_UNIT = '''[Unit]
Description=LAN-only access for 1Panel port 10086
Before=1panel-core.service 1panel-agent.service
After=network-pre.target
[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/sbin/nft -f /etc/hengxin-panel-access.nft
ExecStop=/usr/sbin/nft delete table inet hengxin_panel
[Install]
WantedBy=multi-user.target
'''
DROPIN = '''[Unit]
Requires=hengxin-panel-access.service
After=hengxin-panel-access.service
[Service]
UMask=0077
'''
OVERRIDES = '''
# Deployment-specific safeguards; official binary payload is unchanged.
function Install_Docker() { docker info >/dev/null || exit 1; }
function Set_Firewall() { systemctl is-active --quiet hengxin-panel-access || exit 1; }
function Install_AppStore() { :; }
function Get_Ip() { LOCAL_IP=192.168.1.245; PUBLIC_IP=N/A; }
function install_and_configure() {
 init_configure
 cp ./initscript/1panel-core.service /etc/systemd/system || exit 1
 cp ./initscript/1panel-agent.service /etc/systemd/system || exit 1
 systemctl daemon-reload || exit 1
 systemctl enable 1panel-agent.service 1panel-core.service || exit 1
 systemctl start 1panel-core.service || exit 1
 systemctl start 1panel-agent.service || exit 1
}
main
'''


def run(args, **kwargs):
    return subprocess.run(args, check=True, text=True, capture_output=True,
                          timeout=kwargs.pop('timeout', 30), **kwargs).stdout


def private_write(path, data):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as f:
        f.write(data)


def adapted_installer(raw):
    if hashlib.sha256(raw).hexdigest() != INSTALLER_SHA:
        raise ValueError('installer hash changed')
    text = raw.decode()
    if not text.endswith('main\n'):
        raise ValueError('unexpected entry point')
    text = text[:-5]
    begin, end = text.index('init_configure() {'), text.index('install_and_configure() {')
    original = text[begin:end]
    hardened = []
    for line in original.splitlines():
        if line.strip().startswith(('cp ', 'ln ', 'sed ', 'mkdir ')):
            line += ' || exit 1'
        hardened.append(line)
        if line.strip().startswith('cp ./1pctl '):
            hardened.append('    chmod 700 /usr/local/bin/1pctl || exit 1')
    text = text[:begin] + '\n'.join(hardened) + '\n\n' + text[end:]
    return text + OVERRIDES


def members_checked(archive):
    members = archive.getmembers()
    prefix = PACKAGE.removesuffix('.tar.gz')
    for member in members:
        parts = Path(member.name).parts
        if (not parts or parts[0] != prefix or '..' in parts
                or not (member.isfile() or member.isdir())):
            raise ValueError('unsafe package member')
    return members


def guard():
    if os.geteuid() != 0 or socket.gethostname() != 'hengxin-ai-245':
        raise RuntimeError('wrong execution host')
    for p in (Path('/opt'), Path('/var/lib'), STAGE.parent, STAGE):
        s = p.lstat()
        if not stat.S_ISDIR(s.st_mode) or s.st_uid != 0 or s.st_mode & 0o022:
            raise RuntimeError('unsafe directory')
    if STAGE.stat().st_mode & 0o077:
        raise RuntimeError('staging not private')
    targets = [BASE, Path('/etc/1panel'), Path('/etc/hengxin-panel-access.nft'),
               Path('/etc/systemd/system') / UNIT, Path('/usr/local/bin/lang')]
    for name in ('1panel', '1panel-core', '1panel-agent', '1pctl'):
        targets.extend(Path(d) / name for d in ('/usr/bin', '/usr/local/bin'))
    for name in ('1panel-core', '1panel-agent'):
        targets.extend([Path('/etc/systemd/system') / (name + '.service'),
                        Path('/etc/systemd/system') / (name + '.service.d')])
    if any(os.path.lexists(p) for p in targets):
        raise RuntimeError('installation target already exists; do not overwrite')
    with socket.socket() as probe:
        probe.bind(('0.0.0.0', 10086))
    found = subprocess.run(['/usr/sbin/nft', 'list', 'table', 'inet', 'hengxin_panel'],
                           capture_output=True, timeout=10)
    if found.returncode == 0:
        raise RuntimeError('access table already exists')
    run(['docker', 'info'])
    if hashlib.sha256((STAGE / PACKAGE).read_bytes()).hexdigest() != SHA:
        raise RuntimeError('package checksum mismatch')


def setup_access():
    private_write(Path('/etc/hengxin-panel-access.nft'), RULES)
    run(['/usr/sbin/nft', '-c', '-f', '/etc/hengxin-panel-access.nft'])
    private_write(Path('/etc/systemd/system') / UNIT, ACCESS_UNIT)
    for name in ('1panel-core', '1panel-agent'):
        drop = Path('/etc/systemd/system') / (name + '.service.d')
        drop.mkdir(mode=0o755)
        private_write(drop / 'lan.conf', DROPIN)
    run(['systemctl', 'daemon-reload'])
    run(['systemctl', 'enable', '--now', UNIT])


def stop_failed_panel():
    subprocess.run(['systemctl', 'stop', '1panel-core', '1panel-agent'],
                   capture_output=True, timeout=100)
    run(['systemctl', 'disable', '1panel-core', '1panel-agent'])
    # Revoke only after stopped state and closed listener are observed. Retain
    # restrictions if stop failed, rather than exposing a partly installed panel.
    states = [run(['systemctl', 'show', n, '-p', 'ActiveState', '--value']).strip()
              for n in ('1panel-core', '1panel-agent')]
    listening = run(['ss', '-H', '-ltn', 'sport = :10086']).strip()
    if all(s in ('inactive', 'failed') for s in states) and not listening:
        run(['systemctl', 'disable', '--now', UNIT])


def install():
    os.umask(0o077)
    guard()
    with tarfile.open(STAGE / PACKAGE) as archive:
        members = members_checked(archive)
        extracted = STAGE / PACKAGE.removesuffix('.tar.gz')
        if extracted.exists():
            raise RuntimeError('extraction already exists')
        archive.extractall(STAGE, members=members, filter='data')
    script = adapted_installer((extracted / 'install.sh').read_bytes())
    private_write(extracted / 'install-lan.sh', script)
    run(['/bin/bash', '-n', str(extracted / 'install-lan.sh')])
    private_write(extracted / '.selected_edition', 'cn\n')
    credentials = dict(username='hengxin_admin', password=secrets.token_hex(12),
                       entrance='hx_' + secrets.token_hex(8))
    credentials['url'] = 'http://192.168.1.245:10086/' + credentials['entrance']
    private_write(STAGE / 'credentials.json', json.dumps(credentials))
    env = dict(os.environ, TERM='dumb', PANEL_NON_INTERACTIVE='true', PANEL_LANG='zh',
               PANEL_INSTALL_DIR=str(BASE), PANEL_PORT='10086',
               PANEL_USERNAME=credentials['username'], PANEL_PASSWORD=credentials['password'],
               PANEL_ENTRANCE=credentials['entrance'], PANEL_INSTALL_DOCKER='n',
               PANEL_CONFIGURE_ACCELERATOR='n', PANEL_REPLACE_DAEMON_JSON='n')
    # Output can contain initial credentials; keep it private, never echo it.
    try:
        setup_access()
        with (STAGE / 'install-output.log').open('x') as log:
            result = subprocess.run(['/bin/bash', str(extracted / 'install-lan.sh')],
                                    cwd=extracted, env=env, stdout=log,
                                    stderr=subprocess.STDOUT, timeout=240)
        if result.returncode:
            raise RuntimeError('installer failed; inspect private log')
        for name in ('1panel-core', '1panel-agent'):
            run(['systemctl', 'is-active', '--quiet', name])
        if not (BASE / '1panel/db/core.db').is_file():
            raise RuntimeError('panel initialization not complete')
        for name in ('1panel-core', '1panel-agent'):
            if (hashlib.sha256(Path('/usr/local/bin', name).read_bytes()).digest()
                    != hashlib.sha256((extracted / name).read_bytes()).digest()):
                raise RuntimeError('installed binary mismatch')
        os.chmod('/usr/local/bin/1pctl', 0o700)
        print('PANEL_INSTALLED; browser and baseline verification still required')
    except Exception:
        stop_failed_panel()
        raise


if __name__ == '__main__':
    install()
