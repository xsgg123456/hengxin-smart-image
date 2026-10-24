"""Final references may re-deliver history; snapshots retain filesystem safety."""
import hashlib
import os
from types import SimpleNamespace

import pytest
from PIL import Image

from app.execution.output_collector import OutputCollectionError
from app.overseas.studio.delivery import collect_delivery
from app.overseas.studio import work_baseline
from app.overseas.studio.work_baseline import snapshot_work


@pytest.fixture
def space(tmp_path):
    work, home = tmp_path / 'work', tmp_path / 'home'
    work.mkdir()
    (home / '.codex/generated_images/session').mkdir(parents=True)
    return SimpleNamespace(work=work, home=home, baseline={}, persistent=True)


def picture(path, color='blue'):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new('RGB', (12, 13), color).save(path, compress_level=0)
    return path


def collect(space, text):
    summary = SimpleNamespace(turn_completed=True, error=None, final_text=text,
                              session_id='session')
    return collect_delivery(space, summary)


def link(path):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.symlink_to(path.parent.parent / 'outside.png')
    except OSError:
        pytest.skip('symlink creation not permitted')


def test_snapshot_covers_history_and_research_but_excludes_protected_resources(space):
    paths = ['history/turn-1/a.png', 'research/ref.JPG', 'nested/final.webp']
    for name in paths:
        picture(space.work / name)
    (space.work / 'notes.md').write_text('keep this research note')
    for name in ('inputs/a.png', 'skills/a.png', '.codex/a.png', 'nested/original/a.png'):
        picture(space.work / name)
    baseline = snapshot_work(space.work)
    assert baseline == {os.path.normcase(name).replace('\\', '/'): hashlib.sha256(
        (space.work / name).read_bytes()).hexdigest() for name in paths}


def test_only_explicit_final_work_images_are_delivered_including_history(space):
    picture(space.work / 'old.png')
    picture(space.work / 'history/turn-1/restored.png')
    space.work_baseline = snapshot_work(space.work)
    picture(space.work / 'new.png')
    picture(space.work / 'unreferenced-draft.png')
    outputs, warnings = collect(space, '正式交付：\n![旧](/work/old.png)\n'
                               '![恢复图](/work/history/turn-1/restored.png)\n'
                               '![新图](/work/new.png)')
    assert [target for target, _ in outputs] == [
        '/work/old.png', '/work/history/turn-1/restored.png', '/work/new.png']
    assert warnings == []
    assert [image.data for _, image in outputs] == [
        (space.work / name).read_bytes() for name in
        ('old.png', 'history/turn-1/restored.png', 'new.png')]


def test_content_change_same_path_size_and_mtime_is_new_version(space):
    path = picture(space.work / 'final.png')
    before = path.stat()
    space.work_baseline = snapshot_work(space.work)
    picture(path, 'red')
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert path.stat().st_size == before.st_size
    outputs, warnings = collect(space, '![修改后](/work/final.png)')
    assert warnings == [] and len(outputs) == 1
    assert outputs[0][1].data == path.read_bytes()


def test_final_reference_redelivers_unchanged_bytes_after_metadata_change(space):
    path = picture(space.work / 'old.png')
    space.work_baseline = snapshot_work(space.work)
    raw = path.read_bytes()
    path.unlink()
    path.write_bytes(raw)
    outputs, warnings = collect(space, '![图](/work/old.png)')
    assert [target for target, _ in outputs] == ['/work/old.png']
    assert outputs[0][1].data == raw and warnings == []


def test_rewriting_work_file_does_not_mutate_previous_delivery_bytes(space):
    space.work_baseline = snapshot_work(space.work)
    path = picture(space.work / 'final.png')
    first, warnings = collect(space, '![图](/work/final.png)')
    frozen = first[0][1]
    old_bytes, old_checksum = path.read_bytes(), frozen.checksum
    assert warnings == []
    space.work_baseline = snapshot_work(space.work)
    picture(path, 'red')
    second, warnings = collect(space, '![修改](/work/final.png)')
    assert warnings == [] and len(second) == 1
    assert second[0][1].checksum != old_checksum
    assert frozen.data == old_bytes and frozen.checksum == old_checksum


@pytest.mark.parametrize('target', [
    '/work/inputs/a.png', '/work/skills/a.png', '/work/nested/original/a.png',
    '/home/runner/.codex/generated_images/another/a.png', '/work/../outside.png',
])
def test_protected_and_other_conversation_paths_stay_forbidden(space, target):
    for name in ('inputs/a.png', 'skills/a.png', 'nested/original/a.png'):
        picture(space.work / name)
    picture(space.home / '.codex/generated_images/another/a.png')
    picture(space.work.parent / 'outside.png')
    space.work_baseline = snapshot_work(space.work)
    outputs, warnings = collect(space, f'![图]({target})')
    assert outputs == [] and len(warnings) == 1


def test_final_reference_can_redeliver_unchanged_same_session_native_image(space):
    root = space.home / '.codex/generated_images/session'
    old = picture(root / 'old.png')
    space.baseline = {'old.png': hashlib.sha256(old.read_bytes()).hexdigest()}
    space.work_baseline = snapshot_work(space.work)
    picture(root / 'new.png')
    prefix = '/home/runner/.codex/generated_images/session/'
    outputs, warnings = collect(space, f'![旧]({prefix}old.png)\n![新]({prefix}new.png)')
    assert [target for target, _ in outputs] == [prefix + 'old.png', prefix + 'new.png']
    assert warnings == []
    assert outputs[0][1].data == old.read_bytes()


def test_native_checksum_evidence_still_rejects_changed_bytes(space):
    path = picture(space.home / '.codex/generated_images/session/old.png')
    space.baseline = {'old.png': hashlib.sha256(path.read_bytes()).hexdigest()}
    picture(path, 'red')
    outputs, warnings = collect(space,
        '![图](/home/runner/.codex/generated_images/session/old.png)')
    assert outputs == [] and len(warnings) == 1


@pytest.mark.parametrize('baseline', [None, [], {'old.png': 'broken-hash'},
                                     {'../old.png': 'a' * 64}])
def test_legacy_work_baseline_does_not_gate_final_references(space, baseline):
    path = picture(space.work / 'old.png')
    space.work_baseline = baseline
    outputs, warnings = collect(space, '![图](/work/old.png)')
    assert [target for target, _ in outputs] == ['/work/old.png']
    assert outputs[0][1].data == path.read_bytes() and warnings == []


def test_persistent_workspace_without_snapshot_can_deliver_final_reference(space):
    path = picture(space.work / 'old.png')
    outputs, warnings = collect(space, '![图](/work/old.png)')
    assert [target for target, _ in outputs] == ['/work/old.png']
    assert outputs[0][1].data == path.read_bytes() and warnings == []


def test_bad_image_does_not_hide_valid_explicit_delivery(space):
    space.work_baseline = snapshot_work(space.work)
    (space.work / 'broken.png').write_bytes(b'broken')
    picture(space.work / 'new.png')
    outputs, warnings = collect(space, '![坏](/work/broken.png)\n![好](/work/new.png)')
    assert [target for target, _ in outputs] == ['/work/new.png']
    assert len(warnings) == 1


@pytest.mark.parametrize('operation', ['digest', 'scan'])
def test_snapshot_error_cannot_be_silently_treated_as_no_history(space, monkeypatch, operation):
    picture(space.work / 'old.png')
    def broken(*args, **kwargs):
        raise PermissionError('test unreadable history')
    if operation == 'digest':
        monkeypatch.setattr(work_baseline, '_digest', broken)
    else:
        monkeypatch.setattr(work_baseline.os, 'scandir', broken)
    with pytest.raises(OutputCollectionError, match='work_baseline_failed'):
        snapshot_work(space.work)


def test_missing_work_directory_is_not_an_empty_snapshot(space):
    with pytest.raises(OutputCollectionError, match='work_baseline_failed'):
        snapshot_work(space.work / 'missing')


def test_symlink_and_broken_link_fail_baseline_and_delivery(space):
    space.work_baseline = snapshot_work(space.work)
    picture(space.work.parent / 'outside.png')
    target = space.work / 'link.png'
    link(target)
    for _ in range(2):
        with pytest.raises(OutputCollectionError, match='work_baseline_failed'):
            snapshot_work(space.work)
        outputs, warnings = collect(space, '![图](/work/link.png)')
        assert outputs == [] and len(warnings) == 1
        (space.work.parent / 'outside.png').unlink(missing_ok=True)


def test_linked_parent_directory_is_not_traversed(space):
    other = space.work.parent / 'other-conversation'
    picture(other / 'private.png')
    try:
        (space.work / 'history').symlink_to(other, target_is_directory=True)
    except OSError:
        pytest.skip('directory symlink creation not permitted')
    with pytest.raises(OutputCollectionError, match='work_baseline_failed'):
        snapshot_work(space.work)
    with pytest.raises(OutputCollectionError, match='work_baseline_failed'):
        snapshot_work(space.work / 'history')


def test_hardlinks_fail_baseline_and_delivery(space):
    space.work_baseline = snapshot_work(space.work)
    source = picture(space.work.parent / 'outside.png')
    os.link(source, space.work / 'linked.png')
    with pytest.raises(OutputCollectionError, match='work_baseline_failed'):
        snapshot_work(space.work)
    outputs, warnings = collect(space, '![图](/work/linked.png)')
    assert outputs == [] and len(warnings) == 1


def test_snapshot_reads_fixed_size_chunks(space, monkeypatch):
    raw = b'x' * (2 * 1024 * 1024 + 13)
    (space.work / 'large.png').write_bytes(raw)
    original, reads = work_baseline.os.fdopen, []
    class Metered:
        def __init__(self, stream):
            self.stream = stream
        def __enter__(self):
            return self
        def __exit__(self, *args):
            self.stream.close()
        def fileno(self):
            return self.stream.fileno()
        def read(self, count):
            reads.append(count)
            return self.stream.read(count)
    monkeypatch.setattr(work_baseline.os, 'fdopen', lambda *args: Metered(original(*args)))
    assert snapshot_work(space.work) == {'large.png': hashlib.sha256(raw).hexdigest()}
    assert len(reads) == 4 and set(reads) == {1024 * 1024}


def test_image_modified_during_snapshot_fails_closed(space, monkeypatch):
    path = picture(space.work / 'changing.png')
    original, changed = work_baseline.os.fdopen, []
    class Changing:
        def __init__(self, stream):
            self.stream = stream
        def __enter__(self):
            return self
        def __exit__(self, *args):
            self.stream.close()
        def fileno(self):
            return self.stream.fileno()
        def read(self, count):
            data = self.stream.read(count)
            if not changed:
                with path.open('ab') as writer:
                    writer.write(b'changed during hash')
                changed.append(True)
            return data
    monkeypatch.setattr(work_baseline.os, 'fdopen', lambda *args: Changing(original(*args)))
    with pytest.raises(OutputCollectionError, match='work_baseline_failed'):
        snapshot_work(space.work)


@pytest.mark.skipif(os.name == 'nt', reason='POSIX special-file safety')
def test_special_file_is_rejected_without_blocking(space):
    os.mkfifo(space.work / 'pipe.png')
    with pytest.raises(OutputCollectionError, match='work_baseline_failed'):
        snapshot_work(space.work)


@pytest.mark.skipif(os.name == 'nt', reason='POSIX filename syntax')
def test_unreferenceable_historical_filename_does_not_hide_valid_delivery(space):
    picture(space.work / 'research/url:reference.png')
    space.work_baseline = snapshot_work(space.work)
    picture(space.work / 'new.png')
    outputs, warnings = collect(space, '![好](/work/new.png)\n'
                               '![旧](/work/research/url:reference.png)')
    assert [target for target, _ in outputs] == ['/work/new.png']
    assert len(warnings) == 1
