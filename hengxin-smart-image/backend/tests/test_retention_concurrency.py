"""Retention ownership tested with independent PostgreSQL transactions."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select, text

from app.core.config import get_settings
from app.models import Job, utcnow
from app.modules.api_image_edits.conversation import AdoptTurn, SubmitTurn, adopt, submit
from app.modules.api_image_edits.conversation_models import Conversation, ConversationTurn
from app.modules.api_image_edits.conversation_runtime import claim
from app.modules.api_image_edits.models import ApiFile, ApiItem, ApiTask, ApiVersion
from app.retention import api, legacy, paths
from app.retention.models import RetentionEntry, RetentionObject
from app.retention.state import entry, touch
from app.retention.worker import register_existing, run_once
from test_api_cli_concurrency import pg_edit  # noqa: F401
from test_tasks_concurrency import compete, pg_tasks  # noqa: F401


class Store:
    def __init__(self):
        self.removed = []

    def remove(self, row):
        self.removed.append((row.bucket, row.object_key))


def prepared_api(pg_edit, status='candidate'):
    factory, users, task_id, item_id = pg_edit
    with factory() as session:
        submit(session, users[0], task_id, item_id, SubmitTurn(text='测试意见', baseVersion=1), 'seed')
    now = utcnow()
    with factory.begin() as session:
        turn = session.scalar(select(ConversationTurn))
        conversation = session.get(Conversation, turn.conversation_id)
        conversation.session_id = 'retention-test-session'
        turn.status, turn.finished_at = status, now - timedelta(days=8)
        job = session.get(Job, turn.job_id)
        job.status, job.lease_until, job.execution_count = 'succeeded', None, 2
        source = session.get(ApiFile, turn.base_file_id)
        candidate = ApiFile(id=uuid4(), owner_id=users[0].id, name='candidate.png', bucket=source.bucket,
            object_key=str(uuid4()), content_type='image/png', checksum='b' * 64, size_bytes=2,
            width=8, height=6, status='ready')
        session.add(candidate)
        session.flush()
        turn.candidate_id = candidate.id
        row = entry(session, 'api_cli', conversation.id)
        row.last_activity_at = row.initialized_at = now - timedelta(days=8)
        row.next_cleanup_at = now - timedelta(days=1)
        return now, conversation.id, turn.id, job.id, candidate.id


def workspace(root, identifier):
    directory = root / 'api-edits' / str(identifier)
    directory.mkdir(parents=True)
    (directory / 'history.json').write_text('private history', encoding='utf-8')
    return directory


def test_pg_two_cleaners_expire_once_and_keep_all_formal_data(pg_edit, tmp_path):
    factory, _, task_id, item_id = pg_edit
    now, identifier, _, _, candidate_id = prepared_api(pg_edit)
    directory = workspace(tmp_path, identifier)
    outcomes = compete(lambda _: api.process(factory, Store(), tmp_path, identifier, now))
    assert outcomes.count('expired') == 1
    with factory() as session:
        row = entry(session, 'api_cli', identifier)
        assert row.status == 'expired'
        assert row.counters == {'turns': 1, 'calls': 2}
        assert session.scalar(select(ConversationTurn)) is None
        assert session.get(ApiFile, candidate_id) is None
        assert session.get(ApiTask, task_id).material_id
        item = session.get(ApiItem, item_id)
        assert item.current_version == 1
        assert session.get(ApiFile, item.result_id)
        assert len(session.scalars(select(ApiVersion)).all()) == 1
        assert len(session.scalars(select(RetentionObject)).all()) == 1
    assert not directory.exists()


def test_pg_submit_parent_lock_excludes_cleanup(pg_edit, tmp_path):
    factory, users, task_id, item_id = pg_edit
    now, identifier, _, _, _ = prepared_api(pg_edit)
    directory = workspace(tmp_path, identifier)
    # Hold the same database row used by submission; a second connection must skip it.
    with factory() as session:
        session.scalar(select(ApiTask).where(ApiTask.id == task_id).with_for_update())
        with ThreadPoolExecutor(max_workers=1) as pool:
            assert pool.submit(api.process, factory, Store(), tmp_path, identifier, now).result(10) == 'missing_or_locked'
        submit(session, users[0], task_id, item_id, SubmitTurn(text='新意见', baseVersion=1), 'new')
    assert directory.exists()
    assert api.process(factory, Store(), tmp_path, identifier, utcnow()) == 'not_due'
    with factory() as session:
        assert len(session.scalars(select(ConversationTurn)).all()) == 2


def test_pg_pending_cleanup_fence_rejects_submit_and_claim(pg_edit, tmp_path, monkeypatch):
    factory, users, task_id, item_id = pg_edit
    now, identifier, _, job_id, _ = prepared_api(pg_edit)
    def failed_filesystem(*args, **kwargs):
        raise OSError('isolated filesystem failure')
    monkeypatch.setattr(paths, 'clean', failed_filesystem)
    assert api.process(factory, Store(), tmp_path, identifier, now) == 'retry'
    with factory() as session:
        assert entry(session, 'api_cli', identifier).status == 'expire_pending'
        with pytest.raises(HTTPException) as error:
            submit(session, users[0], task_id, item_id, SubmitTurn(text='不能穿过清理', baseVersion=1), 'blocked')
        assert error.value.status_code == 409
    with pytest.raises(HTTPException) as error:
        claim(factory, job_id)
    assert error.value.status_code == 409
    with factory() as session:
        assert session.get(Job, job_id).execution_count == 2


def test_pg_claim_and_cleanup_compete_without_erasing_running_turn(pg_edit, tmp_path):
    factory, _, _, _ = pg_edit
    now, identifier, turn_id, job_id, _ = prepared_api(pg_edit)
    directory = workspace(tmp_path, identifier)
    with factory.begin() as session:
        turn = session.get(ConversationTurn, turn_id)
        turn.status, turn.finished_at = 'queued', None
        session.get(Job, job_id).status = 'queued'
    outcomes = compete(lambda i: claim(factory, job_id) if i == 0 else api.process(factory, Store(), tmp_path, identifier, now))
    assert outcomes[0] is not None
    assert outcomes[1] in ('protected', 'missing_or_locked')
    with factory() as session:
        assert session.get(ConversationTurn, turn_id).status == 'running'
        assert entry(session, 'api_cli', identifier).status == 'active'
    assert directory.exists()


@pytest.mark.parametrize('adoption_first', [True, False])
def test_pg_adoption_expiration_race_preserves_formal_versions(pg_edit, tmp_path, monkeypatch, adoption_first):
    factory, users, task_id, item_id = pg_edit
    now, identifier, turn_id, _, candidate_id = prepared_api(pg_edit)
    directory = workspace(tmp_path, identifier)
    if adoption_first:
        with factory() as session:
            session.scalar(select(ApiTask).where(ApiTask.id == task_id).with_for_update())
            with ThreadPoolExecutor(max_workers=1) as pool:
                assert pool.submit(api.process, factory, Store(), tmp_path, identifier, now).result(10) == 'missing_or_locked'
            adopt(session, users[0], task_id, item_id, turn_id, AdoptTurn(expectedVersion=1), 'adopt')
        # Once adopted, expiration may remove history but must retain both published versions.
        assert api.process(factory, Store(), tmp_path, identifier, utcnow() + timedelta(days=8)) == 'expired'
        with factory() as session:
            assert session.get(ApiItem, item_id).result_id == candidate_id
            assert session.get(ApiFile, candidate_id)
            assert len(session.scalars(select(ApiVersion)).all()) == 2
            assert session.scalar(select(RetentionObject)) is None
    else:
        entered, release = Event(), Event()
        original = paths.clean
        def delayed(*args, **kwargs):
            entered.set()
            assert release.wait(10)
            return original(*args, **kwargs)
        monkeypatch.setattr(paths, 'clean', delayed)
        def accept():
            with factory() as session:
                try:
                    adopt(session, users[0], task_id, item_id, turn_id, AdoptTurn(expectedVersion=1), 'late-adopt')
                    return 200
                except HTTPException as error:
                    return error.status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            cleanup = pool.submit(api.process, factory, Store(), tmp_path, identifier, now)
            assert entered.wait(10)
            accepted = pool.submit(accept)
            release.set()
            assert cleanup.result(10) == 'expired'
            assert accepted.result(10) in (404, 409)
        with factory() as session:
            item = session.get(ApiItem, item_id)
            assert item.current_version == 1
            assert session.get(ApiFile, item.result_id)
            assert len(session.scalars(select(ApiVersion)).all()) == 1
    assert not directory.exists()


@pytest.mark.parametrize('status', ['queued', 'running', 'collecting', 'cancelling', 'uncertain'])
def test_pg_active_and_uncertain_turns_protect_history(pg_edit, tmp_path, status):
    factory, _, _, _ = pg_edit
    now, identifier, turn_id, job_id, _ = prepared_api(pg_edit, status=status)
    directory = workspace(tmp_path, identifier)
    with factory.begin() as session:
        session.get(Job, job_id).status = status
    assert api.process(factory, Store(), tmp_path, identifier, now) == 'protected'
    with factory() as session:
        assert session.get(ConversationTurn, turn_id)
        assert entry(session, 'api_cli', identifier).status == 'active'
    assert directory.exists()


def test_pg_first_enabled_scan_grants_existing_activity_seven_days(pg_edit, tmp_path, monkeypatch):
    factory, _, _, _ = pg_edit
    now, identifier, turn_id, _, _ = prepared_api(pg_edit)
    directory = workspace(tmp_path, identifier)
    with factory.begin() as session:
        entry(session, 'api_cli', identifier).initialized_at = None
    settings = get_settings()
    monkeypatch.setattr(settings, 'cli_retention_enabled', True)
    monkeypatch.setattr(settings, 'codex_execution_root', str(tmp_path))
    result = run_once(factory, Store(), settings, now)
    assert result['resources'] == []
    register_existing(factory, 25, now + timedelta(days=2))
    with factory() as session:
        row = entry(session, 'api_cli', identifier)
        assert row.initialized_at == row.last_activity_at == now
        assert session.get(ConversationTurn, turn_id)
    assert directory.exists()


@pytest.mark.parametrize('evidence', ['unfinished', 'lease', 'unknown_process'])
def test_pg_terminal_turn_with_unresolved_execution_evidence_is_protected(pg_edit, tmp_path, evidence):
    factory, _, _, _ = pg_edit
    now, identifier, turn_id, job_id, _ = prepared_api(pg_edit)
    directory = workspace(tmp_path, identifier)
    with factory.begin() as session:
        turn = session.get(ConversationTurn, turn_id)
        if evidence == 'unfinished':
            turn.finished_at = None
        elif evidence == 'lease':
            session.get(Job, job_id).lease_until = now - timedelta(hours=1)
        else:
            turn.process_identity = {'node': 'unresolved-other-node', 'pid': 123, 'boot': 'x', 'birth': 'y'}
    assert api.process(factory, Store(), tmp_path, identifier, now) == 'protected'
    assert directory.exists()
    with factory() as session:
        assert session.get(ConversationTurn, turn_id)


@pytest.mark.parametrize('target', ['turn', 'job', 'item'])
def test_pg_unknown_states_preserve_history(pg_edit, tmp_path, target):
    factory, _, _, item_id = pg_edit
    now, identifier, turn_id, job_id, _ = prepared_api(pg_edit)
    directory = workspace(tmp_path, identifier)
    with factory.begin() as session:
        if target == 'turn':
            session.get(ConversationTurn, turn_id).status = 'future_unknown'
        elif target == 'job':
            session.get(Job, job_id).status = 'future_unknown'
        else:
            session.get(ApiItem, item_id).state = 'future_unknown'
    assert api.process(factory, Store(), tmp_path, identifier, now) == 'protected'
    assert directory.exists()
    with factory() as session:
        assert session.get(ConversationTurn, turn_id)
        assert entry(session, 'api_cli', identifier).status == 'active'


