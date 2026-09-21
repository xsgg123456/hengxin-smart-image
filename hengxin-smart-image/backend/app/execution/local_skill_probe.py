"""Use the execution mount/environment, but only run this trusted read-only probe."""
import json
import subprocess
import tempfile
from pathlib import Path

from app.core.config import get_settings
from app.execution.workspace import Workspace, sandbox_command

# -I removes the Skill/current/home directory from Python's module search path.
# find_spec(top-level) does not import package code or parent modules.
PROBE = r'''
import hashlib, importlib.util, json, os, pathlib, shutil, sys
payload = json.load(sys.stdin)
root = pathlib.Path(payload['root'])
entries = {}
for path in sorted(root.rglob('*')):
    name = path.relative_to(root).as_posix()
    if path.is_symlink():
        raise RuntimeError('link')
    if path.is_dir():
        entries[name + '/'] = 'directory'
    elif path.is_file():
        entries[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    else:
        raise RuntimeError('special file')
if entries != payload['files']:
    raise RuntimeError('content drift')
if os.access(root, os.W_OK) or any(os.access(p, os.W_OK) for p in root.rglob('*')):
    raise RuntimeError('writable publication')
for name in payload['requires'].get('executables', []):
    if not shutil.which(name):
        print('缺少隔离环境可执行依赖：' + name)
        sys.exit(2)
for name in payload['requires'].get('pythonModules', []):
    if '.' in name or importlib.util.find_spec(name) is None:
        print('缺少隔离环境 Python 顶层模块：' + name)
        sys.exit(2)
print('ok')
'''


def probe_tree(tree):
    settings = get_settings()
    with tempfile.TemporaryDirectory(prefix='hengxin-skill-check-') as temporary:
        root = Path(temporary)
        home, work, control = (root / name for name in ('home', 'work', 'control'))
        for path in (home, work, control):
            path.mkdir(mode=0o700)
        skill_name = tree.path.name if tree.flat else tree.path.parent.name
        workspace = Workspace(home, work, control, local_skill=tree.path, skill_name=skill_name)
        command = sandbox_command(workspace, settings.codex_binary, [], settings.codex_bwrap_binary)
        command = command[:command.index('--') + 1] + [
            '/usr/bin/python3', '-I', '-c', PROBE]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=30,
                                    input=json.dumps({'root': workspace.skill_path, 'files': tree.files, 'requires': tree.requires}),
                                    close_fds=True)
        except (OSError, subprocess.TimeoutExpired):
            raise ValueError('Skill 隔离环境检查无法启动或超时') from None
        if result.returncode:
            message = result.stdout.strip()
            if result.returncode == 2 and message.startswith('缺少隔离环境'):
                raise ValueError(message[:300])
            raise ValueError('Skill 在真实隔离环境中不可读、内容变化或未只读挂载')
