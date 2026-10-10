"""Exercise the actual retention path boundary without user files."""
from uuid import uuid4
import pytest
from app.retention.paths import clean


def link(path, target):
    try:
        path.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip('Directory symlinks require local OS privilege; exercised on Linux')


@pytest.mark.parametrize('identifier', ['../external', '../../', '/', 'not-a-uuid'])
def test_invalid_identifier_never_deletes_external(tmp_path, identifier):
    root = tmp_path / 'root'
    root.mkdir()
    sentinel = tmp_path / 'external'
    sentinel.write_text('keep')
    with pytest.raises(ValueError):
        clean(root, identifier)
    assert sentinel.read_text() == 'keep'


@pytest.mark.parametrize('location', ['root', 'task', 'cache', 'nested'])
def test_directory_links_protect_external_and_private_files(tmp_path, location):
    root, identifier = tmp_path / 'root', uuid4()
    root.mkdir()
    external = tmp_path / 'external'
    external.mkdir()
    sentinel = external / 'original.png'
    sentinel.write_text('keep')
    task = root / str(identifier)
    if location == 'root':
        alias = tmp_path / 'alias'
        link(alias, root)
        root = alias
    elif location == 'task':
        link(task, external)
    else:
        home = task / 'home/.codex'
        home.mkdir(parents=True)
        if location == 'cache':
            link(home / 'cache', external)
        else:
            (home / 'cache').mkdir()
            link(home / 'cache/nested', external)
    with pytest.raises(ValueError):
        clean(root, identifier, cache_only=location in ('cache', 'nested'))
    assert sentinel.read_text() == 'keep'


def test_only_private_cache_is_removed_then_expiry_is_idempotent(tmp_path):
    identifier = uuid4()
    home = tmp_path / str(identifier) / 'home/.codex'
    for part in ('cache', 'plugins', 'sessions'):
        (home / part).mkdir(parents=True)
        (home / part / 'data').write_text('data')
    shared = tmp_path / 'shared'
    shared.mkdir()
    (shared / 'auth.json').write_text('keep')
    clean(tmp_path, identifier, cache_only=True)
    clean(tmp_path, identifier, cache_only=True)
    assert not (home / 'cache').exists() and not (home / 'plugins').exists()
    assert (home / 'sessions/data').exists()
    clean(tmp_path, identifier)
    clean(tmp_path, identifier)
    assert not home.exists()
    assert (shared / 'auth.json').read_text() == 'keep'
