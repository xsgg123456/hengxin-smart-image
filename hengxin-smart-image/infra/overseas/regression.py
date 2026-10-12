"""Run Linux regressions with this invocation's disposable PostgreSQL and Redis."""
import argparse
from pathlib import Path
import secrets
import subprocess
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('tests', nargs='*')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    prefix = 'hx-overseas-regression-' + secrets.token_hex(6)
    created = []

    def docker(*parts, check=True):
        return subprocess.run(['docker', *parts], check=check, capture_output=True, text=True)

    try:
        docker('network', 'create', '--internal', prefix)
        for suffix, image, options in (
            ('pg', 'postgres:17', ['-e', 'POSTGRES_PASSWORD=isolated-test-only', '-e', 'POSTGRES_DB=hx_test']),
            ('redis', 'redis:7', []),
        ):
            name = prefix + '-' + suffix
            created.append(name)
            docker('run', '-d', '--pull=never', '--name', name, '--network', prefix,
                   '--network-alias', suffix, *options, image)
        for _ in range(60):
            if docker('exec', created[0], 'pg_isready', '-U', 'postgres', check=False).returncode == 0:
                break
            time.sleep(.5)
        else:
            raise RuntimeError('Isolated PostgreSQL failed to start')
        url = 'postgresql+psycopg://postgres:isolated-test-only@pg/hx_test'
        variables = ['-e', 'PYTHONDONTWRITEBYTECODE=1', '-e', 'PYTHONPYCACHEPREFIX=/tmp/pycache', '-e', 'PYTHONUNBUFFERED=1',
                     '-e', 'PYTHONPATH=/workspace/backend', '-e', 'TEST_IDENTITY_REDIS_URL=redis://redis:6379/15']
        for key in ('TEST_DATABASE_URL', 'API_IMAGE_TEST_DATABASE_URL', 'TEST_OVERSEAS_DATABASE_URL',
                    'TEST_OVERSEAS_MEMBERS_DATABASE_URL'):
            variables += ['-e', key + '=' + url]
        name = prefix + '-tests'
        created.append(name)
        result = subprocess.run(['docker', 'run', '--init', '--name', name, '--network', prefix,
            '-v', str(root) + ':/workspace:ro', '-w', '/workspace/backend', *variables,
            'hengxin-smart-image-backend:phase20', '/app/.venv/bin/python', '-m', 'pytest',
            '-q', '-p', 'no:cacheprovider', *args.tests])
        return result.returncode
    finally:
        for name in reversed(created):
            docker('rm', '-fv', name, check=False)
        docker('network', 'rm', prefix, check=False)
        print('CLEANED ' + prefix, flush=True)


if __name__ == '__main__':
    raise SystemExit(main())
