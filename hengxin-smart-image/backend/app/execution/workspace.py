"""Task-private material and an allowlisted outer Linux filesystem."""
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID
from urllib.parse import urlsplit
from .prompts import prompt_for


@dataclass
class Workspace:
    home: Path
    work: Path
    control: Path
    local_skill: Path | None = None
    skill_name: str = 'skill'
    use_skill: bool = True

    @property
    def skill_path(self):
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,99}', self.skill_name):
            raise ValueError('Invalid task Skill directory identifier')
        return '/work/skills/' + self.skill_name


def prepare_workspace(root, task_id, round_id, auth_file):
    root = Path(root).resolve()
    task = root / str(UUID(str(task_id)))
    home, work = task / 'home', task / 'rounds' / str(UUID(str(round_id)))
    control = task / 'control' / str(UUID(str(round_id)))
    for path in (task, home, work, control):
        if path.is_symlink():
            raise ValueError('Execution directory cannot be a symlink')
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not path.resolve().is_relative_to(root):
            raise ValueError('Execution directory escaped root')
        path.chmod(0o700)
    codex_home = home / '.codex'
    if codex_home.is_symlink():
        raise ValueError('Codex home cannot be a symlink')
    codex_home.mkdir(exist_ok=True, mode=0o700)
    auth = codex_home / 'auth.json'
    if auth.is_symlink():
        raise ValueError('Auth file cannot be a symlink')
    if not auth.exists():
        # No shared writable auth/session home between tasks.
        with auth.open('xb') as output:
            output.write(Path(auth_file).read_bytes())
        auth.chmod(0o600)
    config = codex_home / 'config.toml'
    if config.is_symlink() or (config.exists() and config.stat().st_nlink != 1):
        raise ValueError('Config file cannot be a link')
    config.write_text('[features]\nimage_generation = true\n')
    return Workspace(home, work, control)


def sandbox_command(workspace, binary, arguments, bwrap='/opt/hengxin-runtime/bwrap'):
    if os.name != 'posix' or not Path(bwrap).is_file():
        raise RuntimeError('Linux Bubblewrap is required for Codex isolation')
    binary = Path(binary).resolve(strict=True)
    helper = binary.parent / 'codex-code-mode-host'
    if not helper.is_file() or helper.is_symlink():
        raise RuntimeError('Codex code-mode helper is required beside the CLI')
    argv = [bwrap, '--die-with-parent', '--new-session', '--unshare-user',
            '--unshare-pid', '--unshare-ipc', '--unshare-uts', '--cap-drop', 'ALL',
            '--clearenv', '--setenv', 'HOME', '/home/runner',
            '--setenv', 'CODEX_HOME', '/home/runner/.codex',
            '--setenv', 'PATH', '/usr/bin:/bin', '--setenv', 'LANG', 'C.UTF-8',
            '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp']
    proxy = os.environ.get('HENGXIN_CODEX_PROXY_URL', '')
    if proxy:
        parsed = urlsplit(proxy)
        if (os.environ.get('APP_ENV') not in ('test', 'development')
                or parsed.scheme not in ('http', 'https')
                or parsed.hostname not in ('127.0.0.1', 'localhost', '::1')
                or not parsed.port or parsed.username is not None or parsed.password is not None
                or parsed.path not in ('', '/') or parsed.query or parsed.fragment
                or any(c.isspace() for c in proxy)):
            raise ValueError('Invalid local development proxy configuration')
        for key, value in [('HTTP_PROXY', proxy), ('HTTPS_PROXY', proxy),
                           ('NO_PROXY', 'localhost,127.0.0.1,::1')]:
            argv += ['--setenv', key, value, '--setenv', key.lower(), value]
    for name in ('/usr', '/bin', '/lib', '/lib64'):
        if Path(name).exists():
            argv += ['--ro-bind', name, name]
    for name in ('/etc/ssl', '/etc/resolv.conf', '/etc/hosts', '/etc/nsswitch.conf'):
        if Path(name).exists():
            argv += ['--ro-bind', name, name]
    argv += ['--bind', str(workspace.home), '/home/runner',
             '--bind', str(workspace.work), '/work']
    skill = workspace.local_skill or workspace.work / 'skills' / workspace.skill_name
    agents = workspace.home / '.agents'
    if agents.is_symlink() or (hasattr(agents, 'is_junction') and agents.is_junction()):
        raise ValueError('Skill discovery directory cannot be a link')
    if not workspace.use_skill:
        argv += ['--tmpfs', '/home/runner/.agents']
    elif skill.is_dir():
        # Hide previous per-task discovery state and expose only this frozen Skill.
        argv += ['--ro-bind', str(skill), workspace.skill_path,
                 '--tmpfs', '/home/runner/.agents',
                 '--dir', '/home/runner/.agents/skills',
                 '--ro-bind', str(skill), '/home/runner/.agents/skills/' + workspace.skill_name]
    argv += ['--ro-bind', str(binary), '/opt/codex',
             '--ro-bind', str(helper), '/opt/codex-code-mode-host',
             '--chdir', '/work', '--', '/opt/codex', *arguments]
    return argv
