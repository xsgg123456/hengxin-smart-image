"""Real tool links, preserved image bytes and retry receipts through business APIs."""
from datetime import timedelta
import json
import os
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.execution.cleanup_paths import CleanupSafetyError
from app.modules.api_image_edits.models import ApiFile, ApiItem, ApiTask, ApiVersion
from app.modules.api_image_edits.conversation_models import ConversationTurn
from app.retention import api, paths
from app.retention.observability_models import RetentionRecord, RetentionTotals
from app.retention.state import entry, aware
from files_helpers import files_env
from test_api_image_domain import enabled_api
from test_api_cli_conversation import seed_gate, cli_enabled
from test_api_retention import sample


def tools_in(home):
    directory = home / 'tmp' / 'arg0' / 'codex-arg0YBAINy'
    directory.mkdir(parents=True)
    for name in ('apply_patch', 'applypatch', 'codex-execve-wrapper', 'codex-linux-sandbox'):
        (directory / name).symlink_to('/opt/codex')
    return directory


def formal_snapshot(factory):
    with factory() as session:
        return {
            'files': {(r.id, r.object_key, r.checksum, r.size_bytes) for r in session.scalars(select(ApiFile))},
            'versions': {(r.id, r.file_id) for r in session.scalars(select(ApiVersion))},
            'items': {(r.id, r.source_id, r.result_id, r.current_version) for r in session.scalars(select(ApiItem))},
            'tasks': {(r.id, r.material_id, r.deleted_at) for r in session.scalars(select(ApiTask))},
        }


@pytest.mark.skipif(os.name != 'posix', reason='real production POSIX tool symlinks')
def test_tool_links_cache_then_history_preserves_every_formal_object(files_env, monkeypatch, cli_enabled):
    identifier, _, home, now, _ = sample(files_env, monkeypatch, cli_enabled, adopted=True)
    _, factory, store, _ = files_env
    link_dir = tools_in(home)
    root = Path(cli_enabled.codex_execution_root)
    saved_bytes, saved_metadata = dict(store.objects), formal_snapshot(factory)
    session_bytes = (home / 'sessions' / 'session-single-image.jsonl').read_bytes()
    assert api.process(factory, store, root, identifier, now + timedelta(days=1)) == 'cache_cleared'
    assert (home / 'sessions' / 'session-single-image.jsonl').read_bytes() == session_bytes
    assert (home / 'auth.json').exists() and (link_dir / 'apply_patch').is_symlink()
    assert store.objects == saved_bytes and formal_snapshot(factory) == saved_metadata
    assert api.process(factory, store, root, identifier, now + timedelta(days=3)) == 'expired'
    assert not home.parents[1].exists()
    assert store.objects == saved_bytes and formal_snapshot(factory) == saved_metadata
    assert api.process(factory, store, root, identifier, now + timedelta(days=4)) == 'not_due'
    with factory() as session:
        assert session.scalar(select(ConversationTurn)) is None
        row = entry(session, 'api_cli', identifier)
        assert row.counters == {'turns': 1, 'calls': 1}
        assert aware(row.last_activity_at) == now
        totals = session.get(RetentionTotals, 'api_cli')
        assert (totals.cache_total, totals.history_total) == (1, 1)


def test_filesystem_refusal_preserves_history_and_objects_until_retry(files_env, monkeypatch, cli_enabled, caplog):
    identifier, _, home, now, _ = sample(files_env, monkeypatch, cli_enabled, adopted=True)
    _, factory, store, _ = files_env
    root, expiry = Path(cli_enabled.codex_execution_root), now + timedelta(days=3)
    saved_bytes, saved_metadata = dict(store.objects), formal_snapshot(factory)
    original = paths.clean

    def refuse(*args, **kwargs):
        raise CleanupSafetyError('UNEXPECTED_LINK')

    monkeypatch.setattr(paths, 'clean', refuse)
    assert api.process(factory, store, root, identifier, expiry) == 'retry'
    assert home.exists() and store.objects == saved_bytes
    assert formal_snapshot(factory) == saved_metadata
    with factory() as session:
        assert session.scalar(select(ConversationTurn)) is not None
        row = entry(session, 'api_cli', identifier)
        assert row.status == 'expire_pending' and aware(row.last_activity_at) == now
        record = session.scalar(select(RetentionRecord))
        assert record.result == 'retry' and record.turns_removed == 0 and not record.counted
    payload = json.loads(next(r.getMessage().removeprefix('cleanup_deferred ')
        for r in caplog.records if r.name == 'app.execution.cleanup_diagnostics'))
    assert payload['stage'] == 'history_filesystem' and payload['code'] == 'CLEANUP_UNEXPECTED_LINK'
    assert payload['locations'] and all(not p['module'].startswith('/') for p in payload['locations'])
    monkeypatch.setattr(paths, 'clean', original)
    assert api.process(factory, store, root, identifier, expiry + timedelta(hours=1)) == 'expired'
    assert store.objects == saved_bytes and formal_snapshot(factory) == saved_metadata
    with factory() as session:
        records = session.scalars(select(RetentionRecord)).all()
        assert len(records) == 1 and records[0].counted and records[0].result == 'complete'


def test_database_failure_after_directory_removal_rolls_back_and_recovers(files_env, monkeypatch, cli_enabled, caplog):
    identifier, _, home, now, _ = sample(files_env, monkeypatch, cli_enabled, adopted=True)
    _, factory, store, _ = files_env
    root, expiry = Path(cli_enabled.codex_execution_root), now + timedelta(days=3)
    saved_bytes, saved_metadata = dict(store.objects), formal_snapshot(factory)
    original = api.erase_history

    def fail_after_changes(*args, **kwargs):
        original(*args, **kwargs)
        raise IntegrityError('secret-sql', {'token': 'secret-token'}, RuntimeError('secret-dsn'))

    monkeypatch.setattr(api, 'erase_history', fail_after_changes)
    assert api.process(factory, store, root, identifier, expiry) == 'retry'
    assert not home.exists()  # Filesystem completion must not claim DB completion.
    assert store.objects == saved_bytes and formal_snapshot(factory) == saved_metadata
    with factory() as session:
        assert session.scalar(select(ConversationTurn)) is not None
        assert entry(session, 'api_cli', identifier).counters == {}
        assert not session.scalar(select(RetentionRecord)).counted
    assert 'secret-' not in caplog.text
    payload = json.loads(next(r.getMessage().removeprefix('cleanup_deferred ')
        for r in caplog.records if r.name == 'app.execution.cleanup_diagnostics'))
    assert payload['stage'] == 'history_database' and payload['code'] == 'CLEANUP_DATABASE_CONSTRAINT'
    monkeypatch.setattr(api, 'erase_history', original)
    assert api.process(factory, store, root, identifier, expiry + timedelta(hours=1)) == 'expired'
    assert store.objects == saved_bytes and formal_snapshot(factory) == saved_metadata
    with factory() as session:
        assert entry(session, 'api_cli', identifier).counters == {'turns': 1, 'calls': 1}
        assert session.get(RetentionTotals, 'api_cli').history_total == 1
