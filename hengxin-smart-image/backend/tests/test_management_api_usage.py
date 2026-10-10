from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.modules.api_image_edits.models import ApiItem, ApiTask, ApiVersion
from app.modules.management.api_usage_summary import summarize
from app.resource_models import UserRecord
from files_helpers import files_env
from test_api_image_domain import create, enabled_api

URL = '/api/v1/management/api-usage'


def fact(actor, task, category='api_request', **overrides):
    return dict(key=str(uuid4()), category=category, channel='api', kind='generation',
        task_id=UUID(task), task_name='接口换套图', owner_id=actor, operator_id=actor,
        occurred_at=datetime(2026, 10, 9, 16, tzinfo=timezone.utc),
        completed_at=None, state='succeeded', quantity=1, is_retry=False,
        attribution='verified', **overrides)


def mock_facts(monkeypatch, rows):
    from app.modules.management.api_stats import projection
    monkeypatch.setattr(projection, 'read_facts', lambda session: rows)


def test_summary_unknown_and_cli_clarification_are_not_failed():
    actor, task = uuid4(), str(uuid4())
    rows = [fact(actor, task), fact(actor, task), fact(actor, task)]
    rows[1].update(state='uncertain', is_retry=None)
    rows[2].update(state='retryable', is_retry=True)
    rows += [fact(actor, task, 'cli_round'), fact(actor, task, 'cli_round')]
    rows[3].update(state='waiting_user', channel='cli')
    rows[4].update(state='unverified', quantity=0, channel='cli')
    report = summarize(rows)
    assert (report.apiAttempts, report.apiSucceeded, report.apiFailed, report.apiUnknown) == (3, 1, 1, 1)
    assert report.requestSuccessRate == .5
    assert report.apiRetries == report.apiRetryUnknown == 1
    assert (report.cliStarted, report.cliUnverified, report.cliSucceeded, report.cliFailed) == (1, 1, 1, 0)
    assert report.inputTokens is report.outputTokens is report.cost is None


def test_range_and_paging_use_full_history_inventory_is_independent(files_env, monkeypatch):
    client, factory, _, identity = files_env
    task, _ = create(client, count=2)
    rows = [fact(identity[0], task) for _ in range(3)]
    rows.append(fact(identity[0], task, 'adopt'))
    before_midnight = fact(identity[0], task)
    before_midnight['occurred_at'] = datetime(2026, 10, 9, 15, 59, tzinfo=timezone.utc)
    mock_facts(monkeypatch, rows + [before_midnight])
    with factory.begin() as session:
        items = session.scalars(select(ApiItem)).all()
        items[0].state = 'succeeded'
        items[0].result_id = items[0].source_id
        items[1].state = 'failed'
        items[1].result_id = items[1].source_id  # Older formal result retained after failed revision.
    query = '?from=2026-10-10&to=2026-10-10&pageSize=1'
    first = client.get(URL + query).json()
    second = client.get(URL + query + '&page=2').json()
    assert first['summary'] == second['summary']
    assert first['summary']['apiAttempts'] == 3
    assert first['summary']['adoptions'] == 1
    assert first['total'] == 4 and len(first['events']) == 1
    assert first['events'][0]['id'] != second['events'][0]['id']
    assert first['rows'][0]['date'] == '2026-10-10'
    assert first['inventory']['deliverySuccessRate'] == .5
    assert first['inventory']['withResultImages'] == 2
    outside = client.get(URL + '?from=2030-01-01&category=restore').json()
    assert outside['total'] == 0 and outside['inventory'] == first['inventory']


def test_real_api_projection_soft_delete_and_get_does_not_write(files_env):
    client, factory, _, _ = files_env
    task, _ = create(client, count=1)
    before = client.get(URL)
    assert before.status_code == 200, before.text
    assert before.json()['summary']['tasksCreated'] == 1
    assert before.json()['inventory']['tasks'] == 1
    assert client.delete('/api/v1/api-image-edits/tasks/' + task).status_code == 200
    after = client.get(URL).json()
    assert after['summary']['tasksCreated'] == 1
    assert after['inventory']['tasks'] == 0
    assert after['events'][0]['taskDeleted'] is True


def test_actual_operator_scope_and_unknown_actor_guard(files_env, monkeypatch):
    client, factory, _, identity = files_env
    task, _ = create(client)
    other = UserRecord(id=uuid4(), name='协作者', role='designer', status='active', identity_source='development')
    with factory.begin() as session:
        session.add(other)
    mine, theirs, unknown = [fact(identity[0], task) for _ in range(3)]
    theirs['operator_id'], unknown['operator_id'] = other.id, None
    mock_facts(monkeypatch, [mine, theirs, unknown])
    report = client.get(URL).json()
    assert report['summary']['apiAttempts'] == 1 and len(report['users']) == 1
    assert client.get(URL + f'?userId={other.id}').status_code == 403
    assert client.get(URL + '?unassigned=true').status_code == 403
    with factory.begin() as session:
        session.get(UserRecord, identity[0]).role = 'super_admin'
    report = client.get(URL + f'?userId={other.id}').json()
    assert report['summary']['apiAttempts'] == 1 and report['inventory']['tasks'] == 0
    report = client.get(URL + '?unassigned=true').json()
    assert report['summary']['apiAttempts'] == 1 and report['rows'][0]['userId'] is None
    assert report['inventory']['tasks'] == 1


def test_unproven_historical_versions_do_not_inflate_generation_or_adoption(files_env):
    from app.modules.management.api_stats.backfill import preserve
    client, factory, _, identity = files_env
    create(client, count=1)
    with factory.begin() as session:
        item = session.scalar(select(ApiItem))
        for number, kind in enumerate((None, 'image_edit', 'generation'), start=1):
            session.add(ApiVersion(item_id=item.id, number=number, file_id=item.source_id,
                                   operator_id=identity[0], kind=kind))
    before = client.get(URL).json()
    assert before['summary']['generatedVersions'] == 1
    assert before['summary']['unverifiedVersions'] == 2
    assert before['summary']['adoptions'] == 0
    with factory.begin() as session:
        preserve(session)
    after = client.get(URL).json()
    assert after['summary'] == before['summary']
    unknown = [e for e in after['events'] if e['category'] == 'version_published' and e['channel'] == 'unknown']
    assert len(unknown) == 2 and all(e['kind'] == 'legacy_unknown' for e in unknown)


@pytest.mark.parametrize('query', ['from=2026-2-1', 'from=2026-10-11&to=2026-10-10',
    'page=0', 'pageSize=101', 'category=initial', 'userId=invalid'])
def test_invalid_queries(files_env, query):
    client, _, _, _ = files_env
    assert client.get(URL + '?' + query).status_code == 422
