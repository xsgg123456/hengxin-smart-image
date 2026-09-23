"""Publish retained asset set and atomic HTML entry point after backend validation."""
import json
import os
from pathlib import Path
import shutil
import sys

source, app = map(Path, sys.argv[1:3])
dist = source / 'frontend/dist'
target = app / 'frontend/dist'
for path in dist.rglob('*'):
    if not path.is_file() or path.name in ('index.html', 'index.html.gz'):
        continue
    dest = target / path.relative_to(dist)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, dest)
    dest.chmod(0o644)
for directory in target.rglob('*'):
    if directory.is_dir():
        directory.chmod(0o755)
# Avoid serving a previous compressed entry point when the build no longer emits it.
if not (dist / 'index.html.gz').exists():
    (target / 'index.html.gz').unlink(missing_ok=True)
for name in ('index.html.gz', 'index.html'):
    path = dist / name
    if path.exists():
        temporary = target / (name + '.release-new')
        shutil.copyfile(path, temporary)
        temporary.chmod(0o644)
        os.replace(temporary, target / name)
shutil.copyfile(source / 'frontend/package.json', app / 'frontend/package.json')
manifest = json.loads((source / 'release.json').read_text())
manifest['composeOverride'] = sys.argv[3]
manifest['composeBaseOverlays'] = [
    '/opt/hengxin-releases/three-fixes-20260923/api-override.yaml',
    '/opt/hengxin-releases/cli-two-hour-20260923/api-override.yaml',
]
for name in ('API_RELEASE.json', 'API_IMAGE_RELEASE.json', 'FRONTEND_RELEASE.json'):
    temporary = app / (name + '.new')
    temporary.write_text(json.dumps(manifest, indent=2))
    os.replace(temporary, app / name)
native = dict(manifest)
native['files'] = {name: digest for name, digest in manifest['files'].items()
                   if name in ('backend/app/execution/prompts.py', 'backend/app/image_revision_prompt.py')}
temporary = app / 'NATIVE_IMAGE_INPUTS_RELEASE.json.new'
temporary.write_text(json.dumps(native, indent=2))
os.replace(temporary, app / 'NATIVE_IMAGE_INPUTS_RELEASE.json')
