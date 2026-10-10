"""Only UUID children of a configured private execution root can be reclaimed."""
import shutil
from pathlib import Path
from uuid import UUID


def clean(root, resource_id, cache_only=False):
    root = Path(root).absolute()
    target = root / str(UUID(str(resource_id)))
    if root.resolve() != root or target.resolve() != target:
        raise ValueError('Linked execution root')
    if target.parent != root:
        raise ValueError('Invalid execution target')
    paths = [target / 'home' / '.codex' / c for c in ('cache', 'plugins')] if cache_only else [target]
    for path in paths:
        if path.resolve() != path:
            raise ValueError('Linked cleanup target')
        if not path.exists():
            continue
        if not path.is_dir():
            raise ValueError('Cleanup target is not a directory')
        # Reject directory junctions and symlinks; never traverse external material.
        for child in path.rglob('*'):
            if child.is_symlink() or child.is_junction():
                raise ValueError('Linked cleanup material')
    for path in paths:
        if path.exists():
            shutil.rmtree(path)
