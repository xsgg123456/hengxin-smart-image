"""Real local business transactions with fake relay/CLI, never production resources."""
from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4
from sqlalchemy import delete, select
from app.models import utcnow
from app.resource_models import UserRecord
from app.modules.api_image_edits import conversation_runner as runner
from app.modules.api_image_edits.models import ApiAttempt, ApiItem, ApiTask
from app.modules.api_image_edits.conversation_models import ConversationTurn
from app.modules.api_image_edits.execution import execute_next
from app.modules.api_image_edits.relay import RelayError
from app.modules.management.api_stats.models import ApiUsageFact
from app.modules.management.api_stats.projection import read_facts
from app.modules.management.api_stats.backfill import preserve
from app.retention import api
from app.retention.state import aware, entry
from files_helpers import files_env
from test_api_image_domain import ROOT, create, enabled_api
from test_api_image_execution import Client, due
from test_api_image_versions import setup_result, post
from test_api_cli_conversation import seed_gate, cli_enabled, submit, fake_executor, run


def category(factory, name):
    with factory() as session:
        return [r for r in read_facts(session) if r['category'] == name]


def test_retry_freezes_actor_and_preserves_prior_attempt(files_env):
    client, factory, store, identity = files_env
    creator = identity[0]
    task, _ = create(client, 1)
    relay = Client([RelayError('retryable', 'HTTP_429', 'safe')] * 4)
    for _ in range(4):
        assert execute_next(factory, store, relay)
        due(factory)
    first = category(factory, 'api_request')[0]
    assert first['operator_id'] == creator and first['is_retry'] is False
    with factory.begin() as session:
        editor = UserRecord(id=uuid4(), name='重试者', role='operator', status='active', identity_source='development')
        session.add(editor)
        identity[0] = editor.id
    assert post(client, ROOT + '/tasks/' + task + '/retry', key='retry').status_code == 202
    assert post(client, ROOT + '/tasks/' + task + '/retry', key='retry').status_code == 202
    assert execute_next(factory, store, Client())
    rows = sorted(category(factory, 'api_request'), key=lambda r: r['occurred_at'])
    assert len(rows) == 5 and rows[0] == first
    assert rows[-1]['operator_id'] == identity[0] and rows[-1]['is_retry'] is True
    assert rows[-1]['state'] == 'succeeded' and rows[-1]['attribution'] == 'verified'
    assert len(category(factory, 'task_created')) == 1


def test_read_has_no_writes_backfill_idempotent_and_legacy_unknown(files_env):
    client, factory, _, _ = files_env
    task_id, _ = create(client, 1)
    with factory.begin() as session:
        session.execute(delete(ApiUsageFact))
        item = session.scalar(select(ApiItem))
        session.add(ApiAttempt(item_id=item.id, operator_id=session.get(ApiTask, item.task_id).owner_id,
                               state='succeeded', completed_at=utcnow()))
    with factory.begin() as session:
        from sqlalchemy import event
        statements = []
        def observe(conn, cursor, statement, params, context, many):
            statements.append(statement.strip().split()[0].upper())
        engine = session.get_bind()
        event.listen(engine, 'before_cursor_execute', observe)
        try:
            rows = read_facts(session)
        finally:
            event.remove(engine, 'before_cursor_execute', observe)
        assert set(statements) <= {'SELECT'}
        attempt = next(r for r in rows if r['category'] == 'api_request')
        assert attempt['is_retry'] is None and attempt['kind'] == 'legacy_unknown'
        assert attempt['attribution'] == 'historical_unverified'
        assert preserve(session) == 2
        assert preserve(session) == 0
        assert len(read_facts(session)) == 2
        session.get(ApiTask, UUID(task_id)).deleted_at = utcnow()
    assert len(category(factory, 'api_request')) == 1
    assert not ApiUsageFact.__table__.foreign_keys
    assert not {'prompt', 'text', 'messages', 'result_bytes'} & set(ApiUsageFact.__table__.columns.keys())


def test_spawn_candidate_adopt_restore_and_seven_day_cleanup(files_env, monkeypatch, cli_enabled):
    client, factory, store, _ = files_env
    task_id, _, url = setup_result(client, factory)
    fake_executor(monkeypatch, image=True)
    fake = runner.execute
    def execute(args, prompt, control, timeout, monitor, started):
        started(123, 'isolated-test', 1)
        return fake(args, prompt, control, timeout, monitor, started)
    monkeypatch.setattr(runner, 'execute', execute)
    turn = submit(client, url)
    assert sum(r['quantity'] for r in category(factory, 'cli_round')) == 0
    run(factory, store, turn)
    rounds = category(factory, 'cli_round')
    assert len(rounds) == 1 and rounds[0]['quantity'] == 1 and rounds[0]['state'] == 'candidate'
    assert rounds[0]['attribution'] == 'verified'
    adopt_url = url + '/conversation/turns/' + turn['id'] + '/adopt'
    assert post(client, adopt_url, {'expectedVersion': 1}, 'adopt').status_code == 200
    assert post(client, adopt_url, {'expectedVersion': 1}, 'adopt').status_code == 200
    assert len(category(factory, 'adopt')) == 1
    assert category(factory, 'cli_round')[0]['state'] == 'adopted'
    assert category(factory, 'cli_submission')[0]['state'] == 'submitted'
    assert len(category(factory, 'version_published')) == 1
    assert len(category(factory, 'cli_candidate')) == 1
    assert post(client, url + '/restore', {'version': 1}, 'restore').status_code == 200
    assert post(client, url + '/restore', {'version': 1}, 'restore').status_code == 200
    assert len(category(factory, 'restore')) == 1
    with factory() as session:
        before = {r['key']: r for r in read_facts(session)}
        conversation_id = session.get(ConversationTurn, UUID(turn['id'])).conversation_id
        expiry = aware(entry(session, 'api_cli', conversation_id).last_activity_at) + timedelta(days=7)
    monkeypatch.setattr(api, 'same_process', lambda *args: False)
    assert api.process(factory, store, Path(cli_enabled.codex_execution_root), conversation_id, expiry) == 'expired'
    with factory() as session:
        assert session.get(ConversationTurn, UUID(turn['id'])) is None
        assert {r['key']: r for r in read_facts(session)} == before


def test_claim_or_dispatch_fence_without_spawn_does_not_count_execution(files_env, monkeypatch, cli_enabled):
    client, factory, store, _ = files_env
    _, _, url = setup_result(client, factory)
    def fail_spawn(*args):
        raise OSError('spawn unavailable')
    monkeypatch.setattr(runner, 'execute', fail_spawn)
    turn = submit(client, url)
    run(factory, store, turn)
    rows = category(factory, 'cli_round')
    assert len(rows) == 1 and rows[0]['quantity'] == 0 and rows[0]['state'] == 'unverified'
    assert category(factory, 'cli_candidate') == []


def test_spawn_upgrades_backfilled_unverified_fact(files_env, monkeypatch, cli_enabled):
    from app.modules.management.api_stats.facts import record_turn
    client, factory, _, _ = files_env
    _, _, url = setup_result(client, factory)
    turn = submit(client, url)
    with factory.begin() as session:
        row = session.get(ConversationTurn, UUID(turn['id']))
        row.status, row.started_at = 'running', utcnow() - timedelta(minutes=2)
        row.snapshot = {**row.snapshot, 'executionDispatched': True}
        preserve(session)
        old = next(r for r in read_facts(session) if r['category'] == 'cli_round')
        assert old['quantity'] == 0
        item = session.scalar(select(ApiItem))
        record_turn(session, session.get(ApiTask, item.task_id), row, spawned=True)
        first = next(r for r in read_facts(session) if r['category'] == 'cli_round')
        assert first['quantity'] == 1 and first['attribution'] == 'verified'
        assert first['occurred_at'] > old['occurred_at']
        record_turn(session, session.get(ApiTask, item.task_id), row, spawned=True)
        second = next(r for r in read_facts(session) if r['category'] == 'cli_round')
        assert second == first


def test_historical_submission_never_freezes_a_transient_round_state(files_env, cli_enabled):
    client, factory, _, _ = files_env
    _, _, url = setup_result(client, factory)
    turn = submit(client, url)
    with factory.begin() as session:
        session.execute(delete(ApiUsageFact).where(ApiUsageFact.category == 'cli_submission'))
        row = session.get(ConversationTurn, UUID(turn['id']))
        row.status = 'running'
        preserve(session)
        # Simulate an already-backfilled older transient representation.
        saved = session.scalar(select(ApiUsageFact).where(ApiUsageFact.category == 'cli_submission'))
        saved.state = 'running'
        row.status = 'candidate'
    assert category(factory, 'cli_submission')[0]['state'] == 'submitted'
