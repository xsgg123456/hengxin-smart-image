"""Private SSH transport. Secrets never enter local files or console output."""
import argparse
import hashlib
from pathlib import Path
import shlex
import stat
import sys
import time

import paramiko

ROOT = '/var/lib/hengxin-migration/lan-245'


def connect(source=False):
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    host = '107.172.161.139' if source else '192.168.1.245'
    key = 'codex_vps_20260908_ed25519' if source else 'hengxin_devhub_prod'
    client.connect(host, username='root', key_filename=str(Path.home() / '.ssh' / key),
                   allow_agent=False, look_for_keys=False, timeout=15,
                   banner_timeout=15, auth_timeout=15, channel_timeout=60)
    _, stdout, _ = client.exec_command('hostname', timeout=60)
    actual = stdout.read().decode().strip()
    expected = 'racknerd-058889d' if source else 'hengxin-ai-245'
    if actual != expected:
        client.close()
        raise RuntimeError('host identity mismatch')
    client.get_transport().set_keepalive(20)
    return client


def destination_path(name):
    if not name or '/' in name or '\\' in name or name in {'.', '..'}:
        raise ValueError('destination must be a basename')
    return ROOT + '/' + name


def transfer(command, name, payload=None):
    """Stream a read-only source command into an exclusively created target file."""
    dest = destination_path(name)
    source = connect(True)
    target = connect()
    total = 0
    digest = hashlib.sha256()
    started = last = time.monotonic()
    try:
        sftp = target.open_sftp()
        sftp.get_channel().settimeout(60)
        for directory in ('/var', '/var/lib', '/var/lib/hengxin-migration', ROOT):
            entry = sftp.lstat(directory)
            if (not stat.S_ISDIR(entry.st_mode) or entry.st_uid != 0
                    or entry.st_mode & 0o022):
                raise RuntimeError('unsafe destination ancestor')
        if sftp.normalize(ROOT) != ROOT:
            raise RuntimeError('destination path changed')
        attrs = sftp.lstat(ROOT)
        if attrs.st_uid != 0 or attrs.st_mode & 0o077:
            raise RuntimeError('private destination directory permissions invalid')
        with sftp.open(dest, 'wx') as out:
            sftp.chmod(dest, 0o600)
            stdin, stdout, stderr = source.exec_command(command, timeout=60)
            if payload:
                stdin.write(payload)
                stdin.flush()
            stdin.channel.shutdown_write()
            while True:
                if time.monotonic() - started > 1800:
                    raise TimeoutError('transfer exceeded 30 minute deadline')
                data = stdout.read(1024 * 1024)
                if not data:
                    break
                out.write(data)
                digest.update(data)
                total += len(data)
                if time.monotonic() - last >= 20:
                    print(f'{name}: {total / 1048576:.1f} MiB transferred', flush=True)
                    last = time.monotonic()
            error = stderr.read()
            if stdout.channel.recv_exit_status() != 0 or error:
                # Do not echo source stderr: a command can expose env/data on errors.
                raise RuntimeError('source command failed or warned; candidate not approved')
        _, check, _ = target.exec_command('sha256sum -- ' + shlex.quote(dest), timeout=60)
        actual = check.read().decode().split()[0]
        if actual != digest.hexdigest():
            raise RuntimeError('transport checksum mismatch')
        print(f'{name}: verified {total} bytes sha256={actual} '
              f'in {time.monotonic() - started:.1f}s', flush=True)
    finally:
        source.close()
        target.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('script', type=Path)
    parser.add_argument('destination')
    args = parser.parse_args()
    if args.script.name != 'collect_runtime.py':
        raise ValueError('only the reviewed read-only collector is supported')
    transfer('python3 -B -', args.destination, args.script.read_bytes())


if __name__ == '__main__':
    main()
