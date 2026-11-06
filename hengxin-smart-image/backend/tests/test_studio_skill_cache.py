"""Offline end-to-end material preparation in real conversation workspaces."""
import hashlib
import io
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.execution.workspace import prepare_workspace, sandbox_command
from app.overseas.execution import materials
from app.overseas.studio import context_workspace


def new_workspace(tmp_path, conversation=None, *, persistent=True, history=()):
    workspace = prepare_workspace(tmp_path, conversation or uuid4(), uuid4(), None, copy_auth=False)
    if persistent:
        context_workspace.prepare(workspace, list(history), [],
                                  lambda source: pytest.fail('Unexpected context download'))
    return workspace


def prepare(workspace, skill):
    materials.prepare(SimpleNamespace(payload={'skill': skill, 'prompt': '完整上下文'}), workspace)
    return workspace.local_skill


def fingerprint(root):
    return {p.relative_to(root).as_posix(): (p.read_bytes(), p.stat().st_ino, p.stat().st_mtime_ns)
            for p in root.rglob('*') if p.is_file()}


@pytest.fixture(params=['installed', 'legacy'])
def source(request, monkeypatch):
    """Installed frozen packages and database-frozen text + object-store assets."""
    packages, bodies = {}, {}
    reads = Mock()
    store = Mock()

    def open_asset(asset):
        reads(asset.object_key)
        stream = io.BytesIO(bodies[asset.object_key])
        stream.release_conn = Mock()
        return stream

    store.open.side_effect = open_asset
    monkeypatch.setattr(materials, 'get_store', lambda: store)
    monkeypatch.setattr('app.overseas.management.installed_catalog.frozen_package',
                        lambda skill: packages[skill['installedRelease']])
    def metadata(skill):
        from app.overseas.management.installed_tree import digest
        package = packages[skill['installedRelease']]
        entries = {p: dict(size=len(b), sha256=hashlib.sha256(b).hexdigest()) for p, b in package.files.items()}
        for name in package.files:
            for parent in Path(name).parents:
                if str(parent) != '.':
                    entries[parent.as_posix() + '/'] = {'directory': True}
        return None, dict(name=package.name, checksum=digest(entries), entries=entries), False
    monkeypatch.setattr('app.overseas.management.installed_catalog.frozen_item', metadata)

    def skill(name='A', files=None, binary=b'\x00\xffreference'):
        files = files or {'SKILL.md': '完整技能说明', 'scripts/run.py': 'print("first")\n'}
        if request.param == 'installed':
            key = str(uuid4())
            packages[key] = SimpleNamespace(name=name, files={
                **{p: text.encode() for p, text in files.items()}, 'assets/ref.bin': binary})
            return {'name': name, 'installedRelease': key}
        key = str(uuid4())
        bodies[key] = binary
        return dict(name=name, files=files, assets={'assets/ref.bin': dict(
            bucket='offline-test', objectKey=key, sizeBytes=len(binary),
            checksum=hashlib.sha256(binary).hexdigest())})

    return SimpleNamespace(skill=skill, reads=reads, store=store, kind=request.param)


def test_reuse_switch_and_republished_content_preserve_identity(tmp_path, source):
    first = new_workspace(tmp_path)
    root = prepare(first, source.skill())
    original = fingerprint(root)
    conversation = first.home.parent.name
    second = new_workspace(tmp_path, conversation)
    assert prepare(second, source.skill()) == root  # Different release/object key, same bytes.
    assert fingerprint(root) == original
    other = new_workspace(tmp_path, conversation)
    other_root = prepare(other, source.skill('B'))
    assert other_root != root
    resumed = new_workspace(tmp_path, conversation)
    assert prepare(resumed, source.skill()) == root
    assert fingerprint(root) == original
    assert {p.name for p in root.parent.parent.iterdir()} == {root.parent.name, other_root.parent.name}
    assert source.reads.call_count == (2 if source.kind == 'legacy' else 0)
    assert not (first.round_work / 'skills').exists()


@pytest.mark.parametrize('change', ['text', 'add', 'remove', 'script', 'binary', 'executable_path'])
def test_content_changes_keep_old_version(tmp_path, source, change):
    first = new_workspace(tmp_path)
    files = {'SKILL.md': 'description', 'scripts/run.py': 'print(1)', 'references/old.md': 'reference'}
    root = prepare(first, source.skill(files=files))
    original = fingerprint(root)
    changed = dict(files)
    binary = b'\x00\xffreference'
    if change == 'text':
        changed['SKILL.md'] += ' updated'
    elif change == 'add':
        changed['references/new.md'] = 'new'
    elif change == 'remove':
        del changed['references/old.md']
    elif change == 'script':
        changed['scripts/run.py'] = 'print(2)'
    elif change == 'binary':
        binary = b'new resource'
    else:
        changed['scripts/run.txt'] = changed.pop('scripts/run.py')
    second = new_workspace(tmp_path, first.home.parent.name)
    next_root = prepare(second, source.skill(files=changed, binary=binary))
    assert next_root != root
    assert fingerprint(root) == original
    assert (next_root / 'assets/ref.bin').read_bytes() == binary
    if os.name == 'posix':
        for path in next_root.rglob('*'):
            if path.is_file():
                expected = 0o755 if path.suffix in ('.py', '.sh') else 0o644
                assert path.stat().st_mode & 0o777 == expected


def test_conversations_are_private(tmp_path, source):
    first, second = new_workspace(tmp_path), new_workspace(tmp_path)
    one, two = prepare(first, source.skill()), prepare(second, source.skill())
    assert one != two
    assert one.parent.name == two.parent.name
    assert (one / 'SKILL.md').stat().st_ino != (two / 'SKILL.md').stat().st_ino
    (one / 'SKILL.md').write_text('one changed', encoding='utf-8')
    assert (two / 'SKILL.md').read_text(encoding='utf-8') == '完整技能说明'


def test_history_inputs_work_sessions_and_old_rounds_are_byte_preserved(tmp_path, source):
    first = new_workspace(tmp_path)
    root = prepare(first, source.skill())
    preserved = [first.home / '.codex/sessions/history.jsonl', first.work / '用户工作.md',
                 first.inputs_root / 'old-reference.bin', first.round_work / 'skills/old/SKILL.md',
                 first.round_work / 'outputs/image.png', first.round_work / 'input.json']
    for index, path in enumerate(preserved[:-1]):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f'全部历史内容 {index}\n'.encode() + bytes(range(256)))
    before = {p: p.read_bytes() for p in preserved}
    cached = fingerprint(root)
    history = [{'turn_id': first.round_work.name, 'inputs': []}]
    for skill in (source.skill('B'), None, source.skill()):
        current = new_workspace(tmp_path, first.home.parent.name, history=history)
        prepare(current, skill)
    assert all(p.read_bytes() == content for p, content in before.items())
    assert fingerprint(root) == cached


def test_nonpersistent_execution_keeps_per_round_copy(tmp_path, source):
    first = new_workspace(tmp_path, persistent=False)
    one = prepare(first, source.skill())
    second = new_workspace(tmp_path, first.home.parent.name, persistent=False)
    two = prepare(second, source.skill())
    assert one == first.work / 'skills/A'
    assert two == second.work / 'skills/A'
    assert one != two and (one / 'SKILL.md').read_bytes() == (two / 'SKILL.md').read_bytes()
    assert not (first.home.parent / 'skill-cache').exists()


def test_unselected_skill_creates_no_cache_and_disables_discovery(tmp_path):
    workspace = new_workspace(tmp_path)
    prepare(workspace, None)
    assert not workspace.use_skill and workspace.local_skill is None
    assert not (workspace.home.parent / 'skill-cache').exists()


@pytest.mark.skipif(os.name != 'posix', reason='sandbox_command requires Linux; run in Linux release checks')
def test_sandbox_binds_only_selected_version_read_only(tmp_path, source):
    first = new_workspace(tmp_path)
    old = prepare(first, source.skill('A'))
    selected = new_workspace(tmp_path, first.home.parent.name)
    current = prepare(selected, source.skill('B'))
    binary = tmp_path / 'codex'
    binary.touch()
    (tmp_path / 'codex-code-mode-host').touch()
    bwrap = tmp_path / 'bwrap'
    bwrap.touch()
    argv = sandbox_command(selected, binary, [], str(bwrap))
    binds = [argv[i:i + 3] for i, arg in enumerate(argv) if arg in ('--bind', '--ro-bind')]
    assert ['--ro-bind', str(current), '/work/skills/B'] in binds
    assert ['--ro-bind', str(current), '/home/runner/.agents/skills/B'] in binds
    assert all(str(old) not in bind and str(old.parent.parent) not in bind for bind in binds)
    assert ['--remount-ro', '/work/skills'] == argv[argv.index('--remount-ro'):argv.index('--remount-ro') + 2]
    prepare(selected, None)  # Reusing the object must also hide its stale local_skill.
    argv = sandbox_command(selected, binary, [], str(bwrap))
    assert str(current) not in argv and str(old) not in argv
    for destination in ('/work/skills', '/home/runner/.agents'):
        assert any(argv[i:i + 2] == ['--tmpfs', destination] for i in range(len(argv)))
