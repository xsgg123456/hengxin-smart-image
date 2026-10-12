"""Disposable offline integration topology; remove only this invocation's resources."""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--serve', action='store_true')
    parser.add_argument('--phase18', action='store_true')
    parser.add_argument('--phase19', action='store_true')
    parser.add_argument('--origin')
    args = parser.parse_args()
    phase = '19' if args.phase19 else '18' if args.phase18 else '17'
    prefix = 'hx-p' + phase + '-' + secrets.token_hex(6)
    names = []
    environment = {k: v for k, v in os.environ.items() if not k.startswith(
        ('IDENTITY_', 'OVERSEAS_', 'DATABASE_', 'REDIS_', 'MINIO_'))}

    def docker(*command, check=True):
        result = subprocess.run(['docker', *command], capture_output=True, text=True, env=environment)
        if check and result.returncode:
            raise RuntimeError(result.stderr)
        return result.stdout.strip()

    def start(suffix, image, options=(), command=()):
        name = prefix + '-' + suffix
        names.append(name)
        docker('run', '-d', '--pull=never', '--name', name, '--network', prefix,
               '--network-alias', suffix, *options, image, *command)
        return name

    try:
        docker('network', 'create', *([] if args.serve else ['--internal']), prefix)
        pg = start('postgres', 'postgres:17', ('-e', 'POSTGRES_PASSWORD=p17-only',))
        start('redis', 'redis:7', command=('redis-server', '--save', '', '--appendonly', 'no'))
        for _ in range(60):
            if 'accepting connections' in docker('exec', pg, 'pg_isready', '-U', 'postgres', check=False):
                break
            time.sleep(.5)
        else:
            raise RuntimeError('Disposable PostgreSQL did not start')
        for database in ('domestic', 'overseas'):
            docker('exec', pg, 'createdb', '-U', 'postgres', database)
        options = ['--init', '-v', str(ROOT) + ':/workspace:ro', '-w', '/tmp',
                   '-e', 'PYTHONDONTWRITEBYTECODE=1', '-e', 'PYTHONUNBUFFERED=1']
        if args.serve:
            for port in (8008, 8009, 8010):
                options.extend(('-p', f'127.0.0.1::{port}'))
        runner = start('runner', 'hx-management-test:local', options,
                       ('/app/.venv/bin/python', '/workspace/infra/identity-test/checks.py',
                        *(['--serve'] if args.serve else []),
                        *(['--phase18'] if args.phase18 else []),
                        *(['--phase19'] if args.phase19 else []),
                        *(['--origin', args.origin] if args.origin else [])))
        if args.serve:
            print('LOCAL PORTS ' + docker('port', runner), flush=True)
        status = subprocess.call(['docker', 'logs', '-f', runner])
        result = json.loads(docker('inspect', runner))[0]['State']
        if status or result['ExitCode']:
            raise RuntimeError('Phase ' + phase + ' integration failed')
    finally:
        for name in reversed(names):
            docker('rm', '-fv', name, check=False)
        docker('network', 'rm', prefix, check=False)
        print('CLEANED ' + prefix, flush=True)


if __name__ == '__main__':
    main()
