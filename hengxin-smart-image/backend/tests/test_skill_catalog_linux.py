"""Real flat-layout permission/dependency/isolation checks, without AI or Skill execution."""
import json
import os
import subprocess
import sys

import pytest

from test_local_skills_linux import published

pytestmark = pytest.mark.skipif(os.name != 'posix' or os.environ.get('RUN_LOCAL_SKILL_LINUX') != '1',
    reason='Requires Linux root fixture with read-only nobody Worker and Bubblewrap')


def flat_child(root, code=''):
    script = '''
import os
os.setgroups([])
os.setgid(65534)
os.setuid(65534)
from app.modules.skills.local_tree import inspect_tree
from app.execution.local_skill_probe import probe_tree
from app.core.config import get_settings
tree = inspect_tree(get_settings().local_skill_root, 'demo', None, None, flat=True)
probe_tree(tree)
assert tree.mode == 'text' and tree.flat
assert tree.content['poison.py'].startswith(b'raise RuntimeError')
''' + code
    return subprocess.run([sys.executable, '-c', script], env={**os.environ, 'LOCAL_SKILL_ROOT': str(root),
        'CODEX_BINARY': str(root / 'runtime/codex'), 'CODEX_BWRAP_BINARY': '/usr/bin/bwrap'},
        capture_output=True, text=True, timeout=45)


def flatten(root, path):
    for file in path.iterdir():
        file.rename(path.parent / file.name)
    path.rmdir()
    (root / 'demo/hengxin-skill.json').write_text(json.dumps({'mode': 'text', 'version': '1.2.3',
        'requires': {'executables': ['python3'], 'pythonModules': ['json']}}))
    return root / 'demo'


def test_flat_layout_real_probe_and_complete_bytes(published):
    root, path = published
    flatten(root, path)
    (root / 'demo/poison.py').chmod(0o755)
    result = flat_child(root, '''
import io, zipfile
from uuid import uuid4
from app.worker.skill_sync import snapshot
record, raw = snapshot(tree, uuid4(), 'text')
with zipfile.ZipFile(io.BytesIO(raw)) as archive:
    assert archive.getinfo('poison.py').external_attr >> 16 & 0o111 == 0o111
''')
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('unsafe', ['symlink', 'hardlink', 'fifo', 'writable', 'owned', 'missing_dependency'])
def test_flat_layout_rejects_unsafe_and_unavailable_dependencies(published, unsafe):
    root, path = published
    path = flatten(root, path)
    if unsafe == 'symlink':
        (path / 'link').symlink_to('/etc/passwd')
    elif unsafe == 'hardlink':
        (path / 'link').hardlink_to(path / 'SKILL.md')
    elif unsafe == 'fifo':
        os.mkfifo(path / 'pipe')
    elif unsafe == 'writable':
        (path / 'SKILL.md').chmod(0o666)
    elif unsafe == 'owned':
        os.chown(path / 'SKILL.md', 65534, 65534)
    else:
        (path / 'hengxin-skill.json').write_text(json.dumps({'mode': 'text', 'requires': {
            'executables': ['missing-hengxin-test-tool']}}))
    result = flat_child(root)
    assert result.returncode != 0
    assert any(word in result.stderr for word in ('链接', '特殊', '不可写', '缺少隔离环境'))
