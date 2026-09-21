"""Validate an administrator-owned immutable publication without running its code."""
import hashlib
import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path

from app.contracts.management import SkillRegisterInput
from app.modules.skills.package_validator import MAX_FILES, MAX_TOTAL, MAX_ZIP, validate_files


@dataclass(frozen=True)
class LocalTree:
    path: Path
    checksum: str
    requires: dict
    files: dict[str, str]
    content: dict[str, bytes] | None = None
    description: str = ''
    mode: str | None = None
    flat: bool = False
    permissions: dict[str, int] | None = None


def protected(path, metadata):
    if os.name != 'posix':
        raise ValueError('本地 Skill 权限校验需要 Linux Worker')
    # Owners can chmod a read-only file; ACL/group grants are covered by access().
    if metadata.st_uid == os.geteuid() or os.access(path, os.W_OK):
        raise ValueError('Skill 发布树必须由管理员拥有且 Worker 不可写')


def tree_hash(entries):
    digest = hashlib.sha256()
    for name, value in sorted(entries.items()):
        digest.update(name.encode('utf-8') + b'\0' + value.encode('ascii') + b'\0')
    return digest.hexdigest()


def inspect_tree(root, name, mode, version, expected='', *, flat=False):
    SkillRegisterInput(name=name, mode=mode or 'text', version=version or '0.0.0')
    root = Path(root)
    if not root.is_absolute():
        raise ValueError('Skill 发布根目录必须为绝对路径')
    directory = root / name if flat else root / name / version
    try:
        # Protect all ancestors against replacement, including above the configured root.
        for path in reversed((directory, *directory.parents)):
            info = path.lstat()
            if not stat.S_ISDIR(info.st_mode) or path.is_symlink():
                raise ValueError('Skill 发布目录不允许链接或非目录路径')
            protected(path, info)
        files, entries, permissions, count, total = {}, {}, {}, 0, 0
        pending = [directory]
        while pending:
            parent = pending.pop()
            for path in sorted(parent.iterdir()):
                count += 1
                if count > MAX_FILES:
                    raise ValueError('Skill 文件树条目超过 1000')
                info = path.lstat()
                relative = path.relative_to(directory).as_posix()
                permissions[relative] = stat.S_IMODE(info.st_mode)
                if path.is_symlink() or not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
                    raise ValueError('Skill 不允许链接或特殊文件')
                protected(path, info)
                if stat.S_ISDIR(info.st_mode):
                    entries[relative + '/'] = 'directory'
                    pending.append(path)
                    continue
                if info.st_nlink != 1:
                    raise ValueError('Skill 不允许硬链接')
                total += info.st_size
                if info.st_size > MAX_ZIP or total > MAX_TOTAL:
                    raise ValueError('Skill 文件大小超过限制')
                # Never follow a file replaced by a link during inspection.
                descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
                with os.fdopen(descriptor, 'rb') as stream:
                    before = os.fstat(stream.fileno())
                    if (before.st_dev, before.st_ino) != (info.st_dev, info.st_ino):
                        raise ValueError('Skill 文件树在检查中变化')
                    data = stream.read(MAX_ZIP + 1)
                    after = os.fstat(stream.fileno())
                if len(data) != info.st_size or (after.st_mtime_ns, after.st_ctime_ns) != (before.st_mtime_ns, before.st_ctime_ns):
                    raise ValueError('Skill 文件树在检查中变化')
                files[relative] = data
                entries[relative] = hashlib.sha256(data).hexdigest()
        if 'SKILL.md' not in files:
            raise ValueError('Skill 尚未部署：缺少 SKILL.md')
        checksum = tree_hash(entries)
        if flat:
            checksum = hashlib.sha256((checksum + tree_hash({k: str(v) for k, v in permissions.items()})).encode()).hexdigest()
        if expected and checksum != expected:
            raise ValueError('Skill 内容已变化，请恢复原内容或登记新版本')
        manifest = json.loads(files.get('hengxin-skill.json', b'{}'))
        if not isinstance(manifest, dict):
            raise ValueError('Skill 清单无效')
        declared = manifest.get('mode')
        if declared is not None and declared not in ('wallpaper', 'product', 'text'):
            raise ValueError('Skill 清单处理类型无效')
        actual_mode = mode or declared
        package = validate_files(files, actual_mode, None if flat else version, checksum)
        if package.name != name:
            raise ValueError('SKILL.md 名称与登记标识不匹配')
        return LocalTree(directory, checksum, package.requires, entries, files, package.description, actual_mode, flat, permissions)
    except FileNotFoundError:
        raise ValueError('Skill 尚未部署或文件已缺失') from None
    except PermissionError:
        raise ValueError('Worker 无法读取 Skill 发布目录') from None
    except (UnicodeError, KeyError) as error:
        raise ValueError('Skill 元数据无效') from error
