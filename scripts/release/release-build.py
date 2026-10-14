"""Isolated project Buildx builder; no default-builder cache pruning."""
import json
import os
from pathlib import Path

BUILDER = 'hengxin-release'


def ensure(runner):
    raw = runner('docker', 'buildx', 'ls', '--format', '{{json .Builder}}', capture=True)
    names = [json.loads(line).get('Name', '').rstrip('*') for line in raw.splitlines() if line]
    if BUILDER not in names:
        runner('docker', 'buildx', 'create', '--name', BUILDER, '--driver', 'docker-container')
    check(runner)


def check(runner):
    raw = runner('docker', 'buildx', 'ls', '--format', '{{json .Builder}}', capture=True)
    value = next((json.loads(line) for line in raw.splitlines()
                  if line and json.loads(line).get('Name') == BUILDER), {})
    if value.get('Name') != BUILDER or value.get('Driver') != 'docker-container':
        raise RuntimeError('Unexpected project builder identity or driver')


def build(source, image, runner, no_cache=False):
    if not image.startswith('hengxin-smart-image-backend:'):
        raise ValueError('Not a project image')
    ensure(runner)
    args = ['docker', 'buildx', 'build', '--builder', BUILDER, '--load',
            '--label', 'io.hengxin.project=smart-image', '-t', image]
    if no_cache or os.environ.get('HENGXIN_RELEASE_NO_CACHE') == '1':
        args += ['--no-cache']
    runner(*args, '-f', str(Path(source) / 'infra/Dockerfile.backend'), str(source))
