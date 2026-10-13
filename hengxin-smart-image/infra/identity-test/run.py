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
    parser.add_argument('--phase20', action='store_true')
    parser.add_argument('--phase21', action='store_true')
    parser.add_argument('--phase22', action='store_true')
    parser.add_argument('--phase23', action='store_true')
    parser.add_argument('--phase24', action='store_true')
    parser.add_argument('--phase25', action='store_true')
    parser.add_argument('--requirements', action='store_true')
    parser.add_argument('--delete-skills', action='store_true')
    parser.add_argument('--members', action='store_true')
    parser.add_argument('--origin')
    args = parser.parse_args()
    args.requirements = args.requirements or args.delete_skills
    args.phase24 = args.phase24 or args.phase25
    args.phase23 = args.phase23 or args.phase24
    args.phase22 = args.phase22 or args.phase23
    args.phase21 = args.phase21 or args.phase22
    args.phase20 = args.phase20 or args.phase21 or args.requirements
    phase = '25' if args.phase25 else '24' if args.phase24 else '23' if args.phase23 else '22' if args.phase22 else '21' if args.phase21 else '20' if args.phase20 else '19' if args.phase19 else '18' if args.phase18 else '17'
    prefix = 'hx-' + ('members' if args.members else 'p' + phase) + '-' + secrets.token_hex(6)
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
        if args.phase20:
            for kind in ('domestic', 'overseas'):
                start(kind + '-minio', 'minio/minio:latest',
                      ('-e', 'MINIO_ROOT_USER=' + kind + '-test',
                       '-e', 'MINIO_ROOT_PASSWORD=' + kind + '-phase20-test-only'),
                      ('server', '/data'))
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
        runner = start('runner', os.environ.get('IDENTITY_TEST_IMAGE', 'hx-management-test:local'), options,
                       ('/app/.venv/bin/python', '/workspace/infra/identity-test/checks.py',
                        *(['--serve'] if args.serve else []),
                        *(['--phase18'] if args.phase18 else []),
                        *(['--phase19'] if args.phase19 else []),
                        *(['--phase20'] if args.phase20 else []),
                        *(['--phase21'] if args.phase21 else []),
                        *(['--phase22'] if args.phase22 else []),
                        *(['--phase23'] if args.phase23 else []),
                        *(['--phase24'] if args.phase24 else []),
                        *(['--phase25'] if args.phase25 else []),
                        *(['--requirements'] if args.requirements else []),
                        *(['--delete-skills'] if args.delete_skills else []),
                        *(['--members'] if args.members else []),
                        *(['--origin', args.origin] if args.origin else [])))
        if args.serve:
            print('LOCAL PORTS ' + docker('port', runner), flush=True)
        status = subprocess.call(['docker', 'logs', '-f', runner])
        result = json.loads(docker('inspect', runner))[0]['State']
        if status or result['ExitCode']:
            raise RuntimeError('Phase ' + phase + ' integration failed')
        if args.phase25:
            from database_restore import verify
            verify(pg, environment)
    finally:
        for name in reversed(names):
            docker('rm', '-fv', name, check=False)
        docker('network', 'rm', prefix, check=False)
        print('CLEANED ' + prefix, flush=True)


if __name__ == '__main__':
    main()
