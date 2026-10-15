"""An offline recovery must still tell the next real CLI turn where files are."""
import pytest

from app.overseas.studio import context_workspace as context
from app.overseas.studio import context_fs as fs
from test_studio_context_assets import workspace
from test_studio_context_migration import row, write


@pytest.mark.parametrize('maintenance', [False, True])
def test_recovery_notice_survives_preparation_until_next_dispatched_turn(tmp_path, maintenance):
    old = workspace(tmp_path)
    write(old.work, 'research/notes.txt', b'keep old notes')
    history = [row(old)]
    old.maintenance_recovery = maintenance
    context.prepare(old, history, [], lambda _: pytest.fail())
    next_round = workspace(tmp_path, old.home.parent.name)
    next_history = row(next_round)
    context.prepare(next_round, history, [], lambda _: pytest.fail())
    assert next_round.recovery_notice
    assert (next_round.work / 'research/notes.txt').read_bytes() == b'keep old notes'
    # A failed/cancelled preparation has not dispatched a turn, so it cannot consume the notice.
    retry = workspace(tmp_path, old.home.parent.name)
    context.prepare(retry, history, [], lambda _: pytest.fail())
    assert retry.recovery_notice
    # Once that turn is actually in dispatched DB history, later ordinary turns stay quiet.
    later = workspace(tmp_path, old.home.parent.name)
    context.prepare(later, [*history, next_history], [], lambda _: pytest.fail())
    assert not later.recovery_notice


@pytest.mark.parametrize('failure', ['context-index.json', 'manifest.json'])
def test_incremental_recovery_notice_survives_metadata_failure(tmp_path, monkeypatch, failure):
    old = workspace(tmp_path)
    write(old.work, 'notes.txt', b'first notes')
    history = [row(old)]
    delivered = workspace(tmp_path, old.home.parent.name)
    dispatched = row(delivered)
    context.prepare(delivered, history, [], lambda _: pytest.fail())
    history.append(dispatched)
    quiet = workspace(tmp_path, old.home.parent.name)
    context.prepare(quiet, history, [], lambda _: pytest.fail())
    assert not quiet.recovery_notice
    # A rollback creates a new legacy turn after the previous notice was delivered.
    rollback = workspace(tmp_path, old.home.parent.name)
    write(rollback.work, 'notes.txt', b'rollback notes')
    history.append(row(rollback))
    interrupted = workspace(tmp_path, old.home.parent.name)
    save = fs.save
    def fail_metadata(path, data):
        if path.name == failure:
            raise OSError('interrupted metadata')
        return save(path, data)
    monkeypatch.setattr(fs, 'save', fail_metadata)
    with pytest.raises(OSError, match='interrupted metadata'):
        context.prepare(interrupted, history, [], lambda _: pytest.fail())
    persistent = old.home.parent / 'persistent'
    assert (persistent / 'migration-pending.json').is_file()
    monkeypatch.setattr(fs, 'save', save)
    retry = workspace(tmp_path, old.home.parent.name)
    retry_dispatched = row(retry)
    context.prepare(retry, history, [], lambda _: pytest.fail())
    assert retry.recovery_notice
    assert not (retry.work / 'notes.txt').exists()
    index = fs.load(retry.context_index)
    assert { (retry.work / item['path'].removeprefix('/work/')).read_bytes()
             for item in index['files'] } == {b'first notes', b'rollback notes'}
    assert not (persistent / 'migration-pending.json').exists()
    not_dispatched = workspace(tmp_path, old.home.parent.name)
    context.prepare(not_dispatched, history, [], lambda _: pytest.fail())
    assert not_dispatched.recovery_notice
    later = workspace(tmp_path, old.home.parent.name)
    context.prepare(later, [*history, retry_dispatched], [], lambda _: pytest.fail())
    assert not later.recovery_notice


def test_online_conflict_index_remains_announced_after_undispatched_preparation(tmp_path):
    first = workspace(tmp_path)
    second = workspace(tmp_path, first.home.parent.name)
    write(first.work, 'notes.txt', b'first notes')
    write(second.work, 'notes.txt', b'second notes')
    history = [row(first), row(second)]
    cancelled = workspace(tmp_path, first.home.parent.name)
    context.prepare(cancelled, history, [], lambda _: pytest.fail())
    assert cancelled.recovery_notice
    assert not (cancelled.work / 'notes.txt').exists()
    # The next runner sees only dispatched history when materials/mount/cancellation stopped this one.
    actual = workspace(tmp_path, first.home.parent.name)
    dispatched = row(actual)
    context.prepare(actual, history, [], lambda _: pytest.fail())
    assert actual.recovery_notice and actual.context_index.is_file()
    later = workspace(tmp_path, first.home.parent.name)
    context.prepare(later, [*history, dispatched], [], lambda _: pytest.fail())
    assert not later.recovery_notice
