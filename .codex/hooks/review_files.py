"""Canonical Git/worktree snapshots for the review gate."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess

EXCLUDED = {'.git', 'node_modules', '.venv', '.next', 'build', 'dist',
            'dist-preview', 'output', '.playwright-cli', '__pycache__',
            'coverage', '.pytest_cache'}
RUNTIME = {'.codex/review-state.json', '.codex/.review-state.lock',
           '.codex/.needs-review', '.codex/.review-snapshot.json'}


def controlled(name):
    p = PurePosixPath(name)
    if set(p.parts) & EXCLUDED or name in RUNTIME:
        return False
    if name.startswith('.codex/evolution/'):
        return False
    if name.startswith('.codex/review-state.') and name.endswith('.tmp'):
        return False
    if name.startswith('.agents/') and p.suffix.lower() == '.md':
        return True
    return p.suffix.lower() not in {'.md', '.log'} or p.name in {'AGENTS.md', 'SKILL.md'}


def git(root, *args, input=None, allowed=(0,)):
    result = subprocess.run(['git', '-C', str(root), *args], input=input,
                            capture_output=True, timeout=40)
    if result.returncode not in allowed:
        raise RuntimeError(result.stderr.decode('utf-8', 'replace').strip())
    return result


def digest(data, mode='100644'):
    # Only newline normalization; all other whitespace remains significant.
    if mode != '120000' and b'\0' not in data:
        try:
            data.decode('utf-8')
            data = data.replace(b'\r\n', b'\n')
        except UnicodeDecodeError:
            pass
    return mode + ':' + hashlib.sha256(data).hexdigest()


def identity(files):
    return hashlib.sha256(json.dumps(files, sort_keys=True, ensure_ascii=True,
                                     separators=(',', ':')).encode()).hexdigest()


def entries(root, source):
    if source == 'HEAD':
        head = git(root, 'rev-parse', '--verify', '--quiet', 'HEAD', allowed=(0, 1))
        if head.returncode == 1:
            return {}
        raw = git(root, 'ls-tree', '-r', '-z', 'HEAD').stdout
    else:
        raw = git(root, 'ls-files', '--stage', '-z').stdout
    result = {}
    for row in raw.split(b'\0'):
        if not row:
            continue
        meta, name = row.split(b'\t', 1)
        fields = meta.decode('ascii').split()
        name = os.fsdecode(name)
        if not controlled(name):
            continue
        if source == 'HEAD':
            mode, kind, oid = fields
            if kind != 'blob':
                raise ValueError('不支持子模块快照：' + name)
        else:
            mode, oid, stage = fields
            if stage != '0':
                raise ValueError('索引存在未解决冲突：' + name)
        if mode not in {'100644', '100755', '120000'}:
            raise ValueError('不支持文件模式：' + name)
        result[name] = (mode, oid)
    return result


def git_snapshot(root, source):
    items = entries(root, source)
    if not items:
        return {}
    oids = sorted({value[1] for value in items.values()})
    raw = git(root, 'cat-file', '--batch', input=('\n'.join(oids)+'\n').encode()).stdout
    blobs, cursor = {}, 0
    for oid in oids:
        end = raw.index(b'\n', cursor)
        actual, kind, size = raw[cursor:end].split()
        if actual.decode() != oid or kind != b'blob':
            raise ValueError('Git blob 读取失败')
        cursor = end + 1
        blobs[oid] = raw[cursor:cursor + int(size)]
        cursor += int(size) + 1
    return {name: digest(blobs[oid], mode) for name, (mode, oid) in items.items()}


def safe_path(root, name):
    path = root / name
    for parent in path.parents:
        if parent == root:
            break
        if parent.is_symlink():
            raise ValueError('拒绝通过符号链接目录读取：' + name)
    try:
        path.parent.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError('拒绝读取仓库外路径：' + name) from exc
    return path


def snapshot(root):
    indexed = entries(root, 'index')
    raw = git(root, 'ls-files', '-z', '--cached', '--others', '--exclude-standard').stdout
    filemode = git(root, 'config', '--bool', 'core.filemode', allowed=(0, 1)).stdout.strip() == b'true'
    symlinks = git(root, 'config', '--bool', 'core.symlinks', allowed=(0, 1)).stdout.strip() != b'false'
    result = {}
    for encoded in raw.split(b'\0'):
        name = os.fsdecode(encoded)
        if not name or not controlled(name):
            continue
        path = safe_path(root, name)
        if path.is_symlink():
            result[name] = digest(os.fsencode(os.readlink(path)), '120000')
        elif path.is_file():
            mode = indexed.get(name, ('100644', None))[0]
            if mode == '120000' and not symlinks:
                # Git on Windows may materialize a symlink as target text.
                data = path.read_bytes()
            else:
                if mode == '120000':
                    mode = '100644'
                mode = ('100755' if path.stat().st_mode & 0o111 else '100644') if filemode else mode
                data = path.read_bytes()
            result[name] = digest(data, mode)
        elif path.exists():
            raise ValueError('受控路径不是普通文件：' + name)
    return result


def changes(before, after):
    return sorted(name for name in before.keys() | after.keys() if before.get(name) != after.get(name))
