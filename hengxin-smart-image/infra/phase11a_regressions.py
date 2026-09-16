"""Run no-model regression tests against schemas inside an owned disposable database."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.parse import quote
from uuid import uuid4


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--container', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert re.fullmatch(r'hx-p11a-[0-9a-f]{16}-postgres', args.container)
    docker = shutil.which('docker.exe') or shutil.which('docker')
    data = json.loads(subprocess.check_output([docker, 'inspect', args.container], text=True))[0]
    tag = args.container.removesuffix('-postgres')
    assert data['Config']['Labels'].get('hengxin.phase11a') == tag
    values = dict(item.split('=', 1) for item in data['Config']['Env'] if '=' in item)
    bindings = data['NetworkSettings']['Ports']['5432/tcp']
    assert len(bindings) == 1 and bindings[0]['HostIp'] == '127.0.0.1'
    password, port = values['POSTGRES_PASSWORD'], bindings[0]['HostPort']
    database = 'regression_' + uuid4().hex + '_test'
    subprocess.run([docker, 'exec', args.container, 'createdb', '-U', 'hengxin', database], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f'postgresql+psycopg://hengxin:{quote(password, safe="")}@127.0.0.1:{port}/{database}'
    env = {'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': '/home/hengxin', 'LANG': 'C.UTF-8',
           'PYTHONDONTWRITEBYTECODE': '1', 'TEST_DATABASE_URL': url}
    backend = Path(__file__).resolve().parents[1] / 'backend'
    try:
        result = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider'],
                                cwd=backend, env=env, capture_output=True, text=True, timeout=300)
    finally:
        subprocess.run([docker, 'exec', args.container, 'dropdb', '-U', 'hengxin', database], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    output = (result.stdout + result.stderr).replace(password, '[REDACTED]')
    args.output.write_text(output, encoding='utf-8')
    print(output)
    sys.exit(result.returncode)


if __name__ == '__main__':
    main()
