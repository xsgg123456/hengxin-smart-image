"""Opt-in real Linux isolation: root publishes, nobody checks and runs bwrap."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import pytest

pytestmark = pytest.mark.skipif(
    os.name != 'posix' or os.environ.get('RUN_LOCAL_SKILL_LINUX') != '1',
    reason='Set RUN_LOCAL_SKILL_LINUX=1 on Linux as root; no model calls are made')


@pytest.fixture
def published():
    assert os.geteuid() == 0, 'Root fixture creates administrator-owned publication; probes drop to nobody'
    with tempfile.TemporaryDirectory(prefix='hx-skill-test-', dir='/opt') as temporary:
        root = Path(temporary)
        root.chmod(0o755)
        path = root / 'demo' / '1.0.0'
        path.mkdir(parents=True)
        (path / 'SKILL.md').write_text('---\nname: demo\ndescription: example\n---\n')
        (path / 'poison.py').write_text('raise RuntimeError("Skill code must never execute during checks")')
        (path / 'hengxin-skill.json').write_text(json.dumps({'requires': {
            'executables': ['python3'], 'pythonModules': ['json']}}))
        binary = root / 'runtime'
        binary.mkdir()
        for name in ('codex', 'codex-code-mode-host'):
            shutil.copyfile('/bin/true', binary / name)
            (binary / name).chmod(0o755)
        yield root, path


def child(root, code):
    environment = {**os.environ, 'LOCAL_SKILL_ROOT': str(root),
        'CODEX_BINARY': str(root / 'runtime/codex'), 'CODEX_BWRAP_BINARY': '/usr/bin/bwrap'}
    script = """
import os
os.setgroups([])
os.setgid(65534)
os.setuid(65534)
from app.modules.skills.local_tree import inspect_tree
from app.execution.local_skill_probe import probe_tree
from app.core.config import get_settings
tree = inspect_tree(get_settings().local_skill_root, 'demo', 'text', '1.0.0')
""" + code
    return subprocess.run([sys.executable, '-c', script], env=environment,
                          capture_output=True, text=True, timeout=45)


def test_real_bwrap_reads_and_checks_dependencies_without_running_skill_code(published):
    root, _ = published
    result = child(root, 'probe_tree(tree)\nprint("verified")')
    assert result.returncode == 0, result.stderr
    assert 'verified' in result.stdout


def test_real_sandbox_mount_is_readonly_and_neighbor_is_hidden(published):
    root, path = published
    neighbor = root / 'other/1.0.0'
    neighbor.mkdir(parents=True)
    (neighbor / 'secret').write_text('other task/skill must stay hidden')
    result = child(root, '''
import tempfile, subprocess
from pathlib import Path
from app.execution.workspace import Workspace, sandbox_command
with tempfile.TemporaryDirectory() as temp:
    p = Path(temp)
    for name in ('home', 'work', 'control'):
        (p / name).mkdir()
    workspace = Workspace(p/'home', p/'work', p/'control', tree.path, 'demo')
    settings = get_settings()
    command = sandbox_command(workspace, settings.codex_binary, [], settings.codex_bwrap_binary)
    script = "import pathlib,os; p=pathlib.Path('/work/skills/demo/SKILL.md'); discovered=pathlib.Path('/home/runner/.agents/skills/demo'); assert p.is_file(); assert (discovered/'SKILL.md').read_bytes()==p.read_bytes(); assert (discovered/'poison.py').is_file(); assert not os.access(discovered,os.W_OK); assert not os.access(p,os.W_OK); assert not pathlib.Path(" + repr(str(tree.path.parent.parent / 'other')) + ").exists(); p.write_text('changed')"
    command = command[:command.index('--')+1] + ['/usr/bin/python3','-I','-c',script]
    outcome = subprocess.run(command, capture_output=True, text=True)
    assert outcome.returncode != 0 and 'Read-only file system' in outcome.stderr, outcome.stderr
print('isolated')
''')
    assert result.returncode == 0, result.stderr
    assert 'isolated' in result.stdout
    assert 'name: demo' in (path / 'SKILL.md').read_text()


@pytest.mark.parametrize('unsafe', ['symlink', 'hardlink', 'fifo', 'writable', 'owned'])
def test_rejects_links_special_files_and_worker_mutable_publication(published, unsafe):
    root, path = published
    target = path / 'unsafe'
    if unsafe == 'symlink':
        target.symlink_to('/etc/passwd')
    elif unsafe == 'hardlink':
        target.hardlink_to(path / 'SKILL.md')
    elif unsafe == 'fifo':
        os.mkfifo(target)
    elif unsafe == 'writable':
        (path / 'SKILL.md').chmod(0o666)
    else:
        os.chown(path / 'SKILL.md', 65534, 65534)
        (path / 'SKILL.md').chmod(0o444)
    result = child(root, 'probe_tree(tree)')
    assert result.returncode != 0
    assert any(word in result.stderr for word in ('链接', '特殊', '不可写'))


@pytest.mark.parametrize('requires', [{'executables': ['missing-hx-exe-123']},
                                    {'pythonModules': ['missing_hx_module_123']}])
def test_declared_dependencies_checked_inside_real_sandbox(published, requires):
    root, path = published
    (path / 'hengxin-skill.json').write_text(json.dumps({'requires': requires}))
    result = child(root, 'probe_tree(tree)')
    assert result.returncode != 0 and '缺少隔离环境' in result.stderr
