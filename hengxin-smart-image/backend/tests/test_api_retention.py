"""Real API/runner flow with isolated SQLite and file/object stores; no model calls."""
from datetime import timedelta
from pathlib import Path
from uuid import UUID
import pytest
from sqlalchemy import select
from app.models import Job, utcnow
from app.retention import api, paths
from app.retention.models import RetentionEntry, RetentionObject
from app.retention.objects import retry_objects
from app.retention.state import entry
from app.retention.worker import run_once, register_existing
from app.modules.api_image_edits.conversation_models import Conversation, ConversationTurn, ConversationEvent
from app.modules.api_image_edits.models import ApiFile, ApiVersion
from files_helpers import files_env
from test_api_image_domain import enabled_api
from test_api_image_versions import setup_result, post
from test_api_cli_conversation import seed_gate, cli_enabled, submit, fake_executor, run


def sample(files_env, monkeypatch, cli_enabled, adopted=False):
    client, factory, store, _ = files_env
    task, item, url = setup_result(client, factory)
    fake_executor(monkeypatch, image=True)
    turn = submit(client, url)
    run(factory, store, turn)
    result = client.get(url + '/conversation').json()
    if adopted:
        assert post(client, url + '/conversation/turns/' + turn['id'] + '/adopt',
                    {'expectedVersion': 1}).status_code == 200
    identifier = UUID(result['id'])
    root = Path(cli_enabled.codex_execution_root)
    home = root / 'api-edits' / str(identifier) / 'home' / '.codex'
    for part in ('cache', 'plugins'):
        (home / part).mkdir(exist_ok=True)
        (home / part / 'data').write_text(part)
    with factory() as session:
        now = entry(session, 'api_cli', identifier).last_activity_at
        candidate = session.get(ConversationTurn, UUID(turn['id'])).candidate_id
    from app.retention.state import aware
    return identifier, url, home, aware(now), candidate


def test_cache_boundary_preserves_history_and_resumes(files_env, monkeypatch, cli_enabled):
    identifier, url, home, now, _ = sample(files_env, monkeypatch, cli_enabled)
    client, factory, store, _ = files_env
    assert api.process(factory, store, home.parents[3], identifier, now + timedelta(hours=23)) == 'not_due'
    root = Path(cli_enabled.codex_execution_root)
    assert api.process(factory, store, root, identifier, now + timedelta(days=1)) == 'cache_cleared'
    assert not (home / 'cache').exists() and not (home / 'plugins').exists()
    assert (home / 'sessions' / 'session-single-image.jsonl').exists()
    assert (home / 'auth.json').exists()
    calls = fake_executor(monkeypatch)
    turn = submit(client, url)
    run(factory, store, turn)
    assert 'resume' in calls[0][0] and 'session-single-image' in calls[0][0]
    with factory() as session:
        assert entry(session, 'api_cli', identifier).cache_cleared_at is None


def test_expire_preserves_adopted_versions_inputs_and_restarts_explicitly(files_env, monkeypatch, cli_enabled):
    identifier, url, home, now, candidate = sample(files_env, monkeypatch, cli_enabled, adopted=True)
    client, factory, store, _ = files_env
    before_objects = dict(store.objects)
    root = Path(cli_enabled.codex_execution_root)
    before = client.get(url + '/conversation').json()
    assert api.process(factory, store, root, identifier, now + timedelta(days=7)) == 'expired'
    assert not home.parents[1].exists()
    view = client.get(url + '/conversation').json()
    assert view['retention']['status'] == 'expired' and view['turns'] == []
    assert view['lastEventId'] > before['lastEventId']
    assert store.objects == before_objects
    with factory() as session:
        assert session.get(ApiFile, candidate)
        assert session.scalar(select(ApiVersion).where(ApiVersion.file_id == candidate))
        assert session.scalars(select(ConversationTurn)).all() == []
        assert session.scalars(select(ConversationEvent)).all() == []
        assert session.scalars(select(Job).where(Job.kind == 'api_cli_edit')).all() == []
        assert entry(session, 'api_cli', identifier).counters['calls'] == 1
    assert post(client, url + '/conversation/turns', {'text': 'new', 'baseVersion': 2}).status_code == 409
    assert post(client, url + '/conversation/turns', {'text': 'new', 'restartExpired': True,
                'baseTurnId': before['turns'][0]['id']}).status_code == 409
    calls = fake_executor(monkeypatch)
    response = post(client, url + '/conversation/turns', {'text': 'new', 'baseVersion': 2, 'restartExpired': True})
    assert response.status_code == 202, response.text
    run(factory, store, response.json()['turns'][-1])
    assert 'resume' not in calls[0][0]


def test_unadopted_candidate_deleted_with_retryable_object_receipt(files_env, monkeypatch, cli_enabled):
    identifier, _, _, now, candidate = sample(files_env, monkeypatch, cli_enabled)
    _, factory, store, _ = files_env
    with factory() as session:
        key = session.get(ApiFile, candidate).object_key
    expiry = now + timedelta(days=7)
    assert api.process(factory, store, Path(cli_enabled.codex_execution_root), identifier, expiry) == 'expired'
    with factory() as session:
        assert session.get(ApiFile, candidate) is None
        assert session.scalar(select(RetentionObject).where(RetentionObject.object_key == key))
    store.fail_remove = True
    assert retry_objects(factory, store, now=expiry) == 0
    assert key in store.objects
    store.fail_remove = False
    assert retry_objects(factory, store, now=expiry + timedelta(hours=1)) == 1
    assert key not in store.objects
    assert retry_objects(factory, store, now=expiry + timedelta(hours=2)) == 0


def test_active_and_uncertain_are_protected(files_env, monkeypatch, cli_enabled):
    identifier, url, home, now, _ = sample(files_env, monkeypatch, cli_enabled)
    client, factory, store, _ = files_env
    turn = submit(client, url)
    expiry = now + timedelta(days=8)
    assert api.process(factory, store, Path(cli_enabled.codex_execution_root), identifier, expiry) == 'protected'
    with factory.begin() as session:
        t = session.get(ConversationTurn, UUID(turn['id']))
        t.status = session.get(Job, t.job_id).status = 'uncertain'
    assert api.process(factory, store, Path(cli_enabled.codex_execution_root), identifier, expiry) == 'protected'
    assert home.exists()


def test_filesystem_failure_fences_submit_and_retries(files_env, monkeypatch, cli_enabled):
    identifier, url, home, now, _ = sample(files_env, monkeypatch, cli_enabled)
    client, factory, store, _ = files_env
    real = paths.clean
    monkeypatch.setattr(paths, 'clean', lambda *a, **kw: (_ for _ in ()).throw(OSError('disk')))
    expiry = now + timedelta(days=7)
    assert api.process(factory, store, Path(cli_enabled.codex_execution_root), identifier, expiry) == 'retry'
    assert client.get(url + '/conversation').json()['retention']['status'] == 'expire_pending'
    assert post(client, url + '/conversation/turns', {'text': 'new', 'restartExpired': True}).status_code == 409
    monkeypatch.setattr(paths, 'clean', real)
    assert api.process(factory, store, Path(cli_enabled.codex_execution_root), identifier, expiry) == 'expired'
    assert not home.exists()


def test_old_identity_gets_seven_day_grace_and_disabled_never_connects(files_env, monkeypatch, cli_enabled):
    identifier, _, _, now, _ = sample(files_env, monkeypatch, cli_enabled)
    _, factory, _, _ = files_env
    with factory.begin() as session:
        session.delete(entry(session, 'api_cli', identifier))
    future = now + timedelta(days=50)
    register_existing(factory, 25, future)
    with factory() as session:
        from app.retention.state import aware
        assert aware(entry(session, 'api_cli', identifier).last_activity_at) == future
    assert run_once(settings=cli_enabled) == {'status': 'disabled'}


def test_pre_enable_tracking_gets_grace_only_once(files_env, monkeypatch, cli_enabled):
    identifier, _, _, now, _ = sample(files_env, monkeypatch, cli_enabled)
    _, factory, _, _ = files_env
    future = now + timedelta(days=50)
    register_existing(factory, 25, future)
    register_existing(factory, 25, future + timedelta(days=3))
    with factory() as session:
        from app.retention.state import aware
        row = entry(session, 'api_cli', identifier)
        assert aware(row.last_activity_at) == future
        assert aware(row.initialized_at) == future


def test_thumbnail_lease_keeps_pending_until_safe(files_env, monkeypatch, cli_enabled):
    from app.modules.files.variants import ImageVariants
    identifier, url, _, now, candidate = sample(files_env, monkeypatch, cli_enabled)
    client, factory, store, _ = files_env
    with factory.begin() as session:
        variant = session.get(ImageVariants, ('api-image-edits', candidate))
        variant.lease_until = now + timedelta(days=8)
    expiry = now + timedelta(days=7)
    assert api.process(factory, store, Path(cli_enabled.codex_execution_root), identifier, expiry) == 'retry'
    with factory() as session:
        assert session.get(ApiFile, candidate) is not None
    assert client.get(url + '/conversation').json()['retention']['status'] == 'expire_pending'
    with factory.begin() as session:
        session.get(ImageVariants, ('api-image-edits', candidate)).lease_until = None
    assert api.process(factory, store, Path(cli_enabled.codex_execution_root), identifier, expiry) == 'expired'


def test_cross_item_reference_preserves_unadopted_object(files_env, monkeypatch, cli_enabled):
    from app.modules.api_image_edits.models import ApiItem
    identifier, _, _, now, candidate = sample(files_env, monkeypatch, cli_enabled)
    client, factory, store, _ = files_env
    _, other_item, _ = setup_result(client, factory)
    with factory.begin() as session:
        other = session.get(ApiItem, UUID(other_item['id']))
        other.revision_snapshot = {'fileIds': [str(candidate)]}
        key = session.get(ApiFile, candidate).object_key
    assert api.process(factory, store, Path(cli_enabled.codex_execution_root), identifier,
                       now + timedelta(days=7)) == 'expired'
    with factory() as session:
        assert session.get(ApiFile, candidate) is not None
    retry_objects(factory, store, now=now + timedelta(days=8))
    assert key in store.objects
