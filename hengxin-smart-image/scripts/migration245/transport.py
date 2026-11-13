"""Private intranet SSH transport; the former source migration is retired."""
from pathlib import Path


def connect(source=False):
    # Keep the old argument only to reject stale callers before creating a client.
    if source is not False:
        raise RuntimeError('Public source migration is retired; only connect() to intranet is supported')
    import paramiko

    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    client.connect('192.168.1.245', username='root',
                   key_filename=str(Path.home() / '.ssh' / 'hengxin_devhub_prod'),
                   allow_agent=False, look_for_keys=False, timeout=15,
                   banner_timeout=15, auth_timeout=15, channel_timeout=60)
    _, stdout, _ = client.exec_command('hostname', timeout=60)
    actual = stdout.read().decode().strip()
    if actual != 'hengxin-ai-245':
        client.close()
        raise RuntimeError('host identity mismatch')
    client.get_transport().set_keepalive(20)
    return client


def main():
    raise SystemExit('MIGRATION_RETIRED: use scripts/release/intranet/release.py --scope')


if __name__ == '__main__':
    main()
