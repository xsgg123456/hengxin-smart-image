"""Read every installed Skill in the real Linux CLI sandbox, without a model call."""
import json
import os
import subprocess
import tempfile
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

from app.core.config import get_settings
from app.execution.workspace import Workspace, sandbox_command
from app.overseas.execution.materials import prepare
from .installed_catalog import catalog, freeze, identity, root_config

SCRIPT = '''import hashlib, json, pathlib
expected = json.loads(pathlib.Path('/work/probe.json').read_text())
root = pathlib.Path('/home/runner/.agents/skills')
assert [p.name for p in root.iterdir()] == [expected['name']]
for base in (root / expected['name'], pathlib.Path('/work/skills') / expected['name']):
    actual = {p.relative_to(base).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in base.rglob('*') if p.is_file()}
    assert actual == expected['files']
    try:
        (base / 'SKILL.md').open('ab')
    except OSError:
        pass
    else:
        raise AssertionError('Skill mount must be read-only')
print(json.dumps({'name': expected['name'], 'files': len(expected['files']), 'readOnly': True}))
'''


def probe():
    settings = get_settings()
    release, items = catalog()
    results = []
    # No shared CLI auth/session or production task is opened or modified.
    with tempfile.TemporaryDirectory(prefix='skill-probe-', dir=settings.codex_execution_root) as temporary:
        root = Path(temporary)
        for item in items:
            home, work, control = [root / item['name'] / p for p in ('home', 'work', 'control')]
            for path in (home, work, control):
                path.mkdir(parents=True)
            workspace = Workspace(home, work, control)
            frozen = freeze(identity(item['name']))
            prepare(SimpleNamespace(payload={'skill': frozen}), workspace)
            files = {p.relative_to(workspace.local_skill).as_posix(): sha256(p.read_bytes()).hexdigest()
                     for p in workspace.local_skill.rglob('*') if p.is_file()}
            (work / 'probe.json').write_text(json.dumps(dict(name=item['name'], files=files)), encoding='utf-8')
            command = sandbox_command(workspace, settings.codex_binary, ['-c', SCRIPT], settings.codex_bwrap_binary)
            # Same mount/env/user isolation as CLI, executing only a local read probe.
            command[command.index('--') + 1] = '/usr/bin/python3'
            result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=True)
            results.append(json.loads(result.stdout))
    directory, _ = root_config()
    info = directory.stat()
    return dict(release=release, packages=len(results), uid=os.geteuid(),
                directoryIdentity=dict(device=info.st_dev, inode=info.st_ino),
                files=sum(row['files'] for row in results), results=results)


if __name__ == '__main__':
    print(json.dumps(probe(), ensure_ascii=False))
