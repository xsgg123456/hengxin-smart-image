"""Separate PostgreSQL transactions prove claim/submit/adopt/cleanup exclusion."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from app.core.config import get_settings
from app.models import Job, utcnow
from app.modules.api_image_edits import deletion
from app.modules.api_image_edits.conversation import AdoptTurn, SubmitTurn, adopt, submit
from app.modules.api_image_edits.conversation_models import Conversation, ConversationTurn
from app.modules.api_image_edits.conversation_runtime import claim
from app.modules.api_image_edits.deletion_models import ApiTaskDeletion
from app.modules.api_image_edits.models import ApiFile, ApiTask
from app.retention import api
from test_api_cli_concurrency import pg_edit
from test_tasks_concurrency import compete
from files_helpers import MemoryStore


def config(tmp_path):
    return SimpleNamespace(**{**get_settings().model_dump(), 'codex_execution_root': str(tmp_path)})


def invoke(factory, action):
    with factory() as session:
        try:
            action(session)
            return 202
        except HTTPException as error:
            return error.status_code


def test_pg_submit_and_delete_cannot_both_admit(pg_edit):
    factory, users, task_id, item_id = pg_edit
    actions = [lambda s: deletion.request(s, users[0], task_id),
        lambda s: submit(s, users[1], task_id, item_id, SubmitTurn(text='edit', baseVersion=1), 'parallel')]
    assert sorted(compete(lambda i: invoke(factory, actions[i]))) == [202, 409]
    with factory() as session:
        turn = session.scalar(select(ConversationTurn))
        receipt = session.get(ApiTaskDeletion, task_id)
        assert (turn is None) != (receipt is None)


def terminal(pg_edit):
    factory, users, task_id, item_id = pg_edit
    with factory() as session:
        submit(session, users[0], task_id, item_id, SubmitTurn(text='edit', baseVersion=1), 'seed')
    with factory.begin() as session:
        turn = session.scalar(select(ConversationTurn))
        turn.status, turn.finished_at, turn.candidate_id = 'candidate', utcnow(), turn.base_file_id
        job = session.get(Job, turn.job_id)
        job.status, job.completed_at = 'succeeded', utcnow()
        return turn.id, turn.conversation_id, turn.job_id


def test_pg_delete_fence_blocks_adopt_claim_and_retention(pg_edit, tmp_path):
    factory, users, task_id, item_id = pg_edit
    turn_id, conversation_id, job_id = terminal(pg_edit)
    with factory() as session:
        deletion.request(session, users[0], task_id)
    assert invoke(factory, lambda s: adopt(s, users[0], task_id, item_id, turn_id,
        AdoptTurn(expectedVersion=1), 'late')) == 409
    assert claim(factory, job_id) is None
    assert api.process(factory, MemoryStore(), tmp_path, conversation_id,
        utcnow() + timedelta(days=9)) == 'missing_or_locked'


def test_pg_active_claim_and_delete_never_remove_execution(pg_edit):
    factory, users, task_id, item_id = pg_edit
    with factory() as session:
        submit(session, users[0], task_id, item_id, SubmitTurn(text='edit', baseVersion=1), 'seed')
    with factory() as session:
        job_id = session.scalar(select(ConversationTurn.job_id))
    actions = [lambda: invoke(factory, lambda s: deletion.request(s, users[0], task_id)),
               lambda: claim(factory, job_id)]
    outcomes = compete(lambda i: actions[i]())
    assert outcomes[0] == 409 and outcomes[1] is not None
    with factory() as session:
        assert session.get(Job, job_id).status == 'running'
        assert session.get(ApiTaskDeletion, task_id) is None


def test_pg_two_native_cleaners_and_repeated_request_are_idempotent(pg_edit, tmp_path):
    factory, users, task_id, _ = pg_edit
    store = MemoryStore()
    with factory() as session:
        for record in session.scalars(select(ApiFile)):
            store.objects[record.object_key] = b'x'
    assert compete(lambda _: invoke(factory, lambda s: deletion.request(s, users[0], task_id))) == [202, 202]
    outcomes = compete(lambda _: deletion.process(factory, store, task_id, config(tmp_path)))
    assert outcomes == ['deleted', 'deleted']
    assert store.objects == {}
    with factory() as session:
        assert session.get(ApiTask, task_id) is None
        assert session.get(ApiTaskDeletion, task_id).manifest == {}


def test_pg_frozen_file_rejects_new_task_reference_after_storage_failure(pg_edit, tmp_path):
    from app.modules.api_image_edits.files import find_file
    factory, users, task_id, _ = pg_edit
    store = MemoryStore()
    with factory() as session:
        file_id = session.get(ApiTask, task_id).material_id
        deletion.request(session, users[0], task_id)
    store.fail_remove = True
    assert deletion.process(factory, store, task_id, config(tmp_path)) == 'delete_failed'
    assert invoke(factory, lambda s: find_file(s, file_id, lock=True)) == 404
    store.fail_remove = False
    assert deletion.process(factory, store, task_id, config(tmp_path)) == 'deleted'
