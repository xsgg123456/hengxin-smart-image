"""Read-only host references. Never expose process environments or unit contents."""
import json
import os
from pathlib import Path
import re
import shlex


def unit_configs(u, refs):
    # Ask the running manager: list-units alone omits installed but unloaded units.
    paths = shlex.split(u.run(['systemctl', 'show', '-p', 'UnitPath', '--value']))
    if not paths or any(not Path(p).is_absolute() for p in paths):
        raise RuntimeError('Cannot enumerate systemd unit paths')
    seen, stack = set(), [Path(p) for p in paths]
    while stack:
        folder = stack.pop()
        try:
            info = folder.stat()
        except FileNotFoundError:
            if folder.is_symlink():
                refs.path(str(folder), 'systemd-link')
            continue  # UnitPath includes optional directories not created yet.
        identity = (info.st_dev, info.st_ino)
        if identity in seen:
            continue
        seen.add(identity)
        for path in folder.iterdir():
            if path.is_symlink():
                refs.path(str(path), 'systemd-link')
                if not path.exists():
                    continue  # A dangling unit link cannot load a configuration.
            if path.is_dir():
                stack.append(path)
            elif path.is_file():
                refs.config(path.read_text(errors='replace'), 'systemd-config')


class References:
    def __init__(self, root):
        self.root = root
        self.reasons = {}
        self.pattern = re.compile(re.escape(str(root)) + r'/([a-zA-Z0-9][a-zA-Z0-9_.-]*)')

    def text(self, value, reason):
        for name in self.pattern.findall(value):
            self.reasons.setdefault(str(self.root / name), set()).add(reason)

    def config(self, value, reason):
        self.text(value, reason)
        # Unit paths may name symlink aliases outside the managed source root.
        for path in re.findall(r'''/[^\s;"'(){}\x00=]+''', value):
            self.path(path, reason)

    def path(self, value, reason, parent_mount=False):
        path = Path(value.removesuffix(' (deleted)'))
        if not path.is_absolute():
            return
        for candidate in (path, path.resolve()):
            self.text(str(candidate), reason)
            if parent_mount and (candidate == self.root or candidate in self.root.parents):
                for child in self.root.iterdir():
                    self.reasons.setdefault(str(child), set()).add(reason)


def ledger_refs(refs, data):
    for key in ('current', 'previous'):
        state = data.get(key)
        if not state:
            continue
        for field in ('backend', 'frontend'):
            path = Path(state[field])
            if path.parent != refs.root or path.name.startswith('.') or not path.is_dir():
                raise RuntimeError('Invalid retained release reference')
            refs.path(str(path), key + ':' + field)
        refs.text(json.dumps(state.get('native', {})), key + ':native')
        refs.text(json.dumps(state.get('binaries', {})), key + ':binary')
        for native in state.get('native', {}).values():
            refs.path(native['python'], key + ':interpreter')


def process_refs(refs, proc=Path('/proc')):
    for entry in proc.iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            # Kernel threads have no cwd/exe; a vanished userspace process is harmless.
            command = (entry / 'cmdline').read_bytes()
            if not command:
                continue
            cwd = Path(os.readlink(entry / 'cwd'))
            refs.text(command.decode(errors='replace'), 'process-command')
            for arg in command.decode(errors='replace').split('\0'):
                value = arg.partition('=')[2] if arg.startswith('-') and '=' in arg else arg
                if '/' in value:
                    refs.path(str(Path(value) if value.startswith('/') else cwd/value), 'process-argument')
            environment = (entry / 'environ').read_bytes().decode(errors='replace')
            refs.text(environment, 'process-env')
            for value in environment.split('\0'):
                name, _, content = value.partition('=')
                for part in content.split(':'):
                    if part.startswith('/'):
                        refs.path(part, 'process-env-path')
                    elif part and name in ('PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV', 'NODE_PATH', 'LD_LIBRARY_PATH'):
                        refs.path(str(cwd/part), 'process-env-path')
            for name in ('cwd', 'exe', 'root'):
                refs.path(os.readlink(entry / name), 'process-' + name)
            for fd in (entry / 'fd').iterdir():
                try:
                    refs.path(os.readlink(fd), 'process-fd')
                except FileNotFoundError:
                    pass  # A closed FD must not hide other open descriptors.
            refs.text((entry / 'maps').read_text(), 'process-maps')
        except (FileNotFoundError, ProcessLookupError):
            if entry.exists():
                raise RuntimeError('Process reference inspection incomplete') from None


def mount_refs(refs, content):
    rows = []
    for line in content.splitlines():
        fields = line.split()
        paths = [Path(re.sub(r'\\([0-7]{3})', lambda m: chr(int(m[1], 8)), v))
                 for v in fields[3:5]]
        rows.append((fields[2], *paths))
    bases = [r for r in rows if refs.root.is_relative_to(r[2])]
    if not bases:
        raise RuntimeError('Cannot identify release filesystem mount')
    base = max(bases, key=lambda r: len(r[2].parts))
    for device, source, target in rows:
        refs.text(str(target), 'host-mount')
        if target == refs.root:
            raise RuntimeError('Release root is itself a mount')
        if (device, source, target) == base or device != base[0]:
            continue
        # Translate filesystem-relative mount roots back into the host path. This
        # protects ancestor bind mounts without treating the normal '/' mount as use.
        if source.is_relative_to(base[1]):
            refs.path(str(base[2] / source.relative_to(base[1])), 'host-mount', parent_mount=True)
        elif base[1].is_relative_to(source):
            refs.path(str(refs.root), 'host-mount', parent_mount=True)


def collect(u, data, root):
    refs = References(root)
    ledger_refs(refs, data)
    ids = u.run(['docker', 'ps', '-aq']).split()
    if ids:
        for info in json.loads(u.run(['docker', 'inspect', *ids])):
            for mount in info.get('Mounts', []):
                refs.path(mount['Source'], 'container-mount', parent_mount=True)
    process_refs(refs)
    mount_refs(refs, Path('/proc/self/mountinfo').read_text())
    units = u.run(['systemctl', 'list-units', '--all', '--type=service', '--plain', '--no-legend'])
    names = [line.split()[0] for line in units.splitlines() if line.strip()]
    if names:
        refs.config(u.run(['systemctl', 'show', *names,
                        '--property=ExecStart,ExecStartPre,ExecStartPost,ExecStop,WorkingDirectory,RootDirectory,Environment,EnvironmentFiles']),
                  'systemd-loaded')
    unit_configs(u, refs)
    return {p: sorted(reasons) for p, reasons in refs.reasons.items()}
