"""Copy only validated frozen package bytes into the current private round."""
import os
from pathlib import Path
from app.overseas.management.installed_tree import safe_directory


def write_package(root, files, work):
    work = safe_directory(work)
    if not root.is_relative_to(work):
        raise ValueError('Frozen Skill escaped round directory')
    root.mkdir(parents=True, exist_ok=True)
    safe_directory(root)
    for relative, content in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        safe_directory(target.parent)
        if target.exists() and (target.is_symlink() or target.stat().st_nlink != 1):
            raise ValueError('Frozen Skill target cannot be a link')
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        with os.fdopen(descriptor, 'wb') as output:
            output.write(content)
        target.chmod(0o755 if Path(relative).suffix.lower() in ('.sh', '.py') else 0o644)
