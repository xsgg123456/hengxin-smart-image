"""Generation counts are outputs, not inventory, requests or adoption actions."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.models import utcnow
from app.modules.api_image_edits.execution import execute_next
from app.modules.api_image_edits.models import ApiItem, ApiTask, ApiVersion
from app.modules.api_image_edits.conversation_models import ConversationTurn
from app.modules.management.api_stats.backfill import preserve
from app.modules.management.api_usage_summary import summarize
from app.retention import api
from app.retention.state import aware, entry
from app.resource_models import UserRecord
from files_helpers import files_env
from test_api_image_domain import ROOT, create, enabled_api
from test_api_image_execution import Client
from test_api_image_versions import post
from test_api_cli_conversation import seed_gate, cli_enabled, submit, fake_executor, run
from test_management_api_usage import URL, fact, mock_facts


def totals(client, suffix=''):
    response = client.get(URL + '?outputsOnly=true' + suffix)
    assert response.status_code == 200, response.text
    return response.json()


def test_ten_initial_plus_three_modifications_real_flows(files_env, monkeypatch, cli_enabled):
    client, factory, store, identity = files_env
    task_id, _ = create(client, 10)
    for _ in range(10):
        assert execute_next(factory, store, Client())
    item = client.get(f'{ROOT}/tasks/{task_id}').json()['items'][0]
    path = f"{ROOT}/tasks/{task_id}/items/{item['id']}"
    for version in (1, 2):
        response = post(client, path + '/revise', {'baseVersion': version, 'text': '修改文字', 'kind': 'text_edit'})
        assert response.status_code == 202, response.text
        assert execute_next(factory, store, Client())
    fake_executor(monkeypatch, image=True)
    turn = submit(client, path, baseVersion=3)
    run(factory, store, turn)
    before = totals(client)
    summary = before['summary']
    assert (summary['initialImages'], summary['modifiedImages'], summary['totalGeneratedImages']) == (10, 3, 13)
    assert summary['generatedTasks'] == 1
    assert sum(e['generatedImages'] for e in before['events']) == 13
    assert sum(r['summary']['totalGeneratedImages'] for r in before['rows']) == 13
    assert totals(client, '&generationType=initial')['summary']['totalGeneratedImages'] == 10
    assert totals(client, '&generationType=api_edit')['summary']['totalGeneratedImages'] == 2
    assert totals(client, '&generationType=cli_edit')['summary']['totalGeneratedImages'] == 1
    # Candidate counts before adoption; adopting and restoring do not create images.
    adopt_url = path + '/conversation/turns/' + turn['id'] + '/adopt'
    assert post(client, adopt_url, {'expectedVersion': 3}, 'adopt').status_code == 200
    assert post(client, adopt_url, {'expectedVersion': 3}, 'adopt').status_code == 200
    assert post(client, path + '/restore', {'version': 1}, 'restore').status_code == 200
    assert totals(client)['summary'] == summary
    assert client.get(f'{ROOT}/tasks/{task_id}/zip').status_code == 200
    with factory.begin() as session:
        preserve(session)
        preserve(session)
        conversation_id = session.get(ConversationTurn, UUID(turn['id'])).conversation_id
        expiry = aware(entry(session, 'api_cli', conversation_id).last_activity_at) + timedelta(days=7)
    monkeypatch.setattr(api, 'same_process', lambda *args: False)
    assert api.process(factory, store, Path(cli_enabled.codex_execution_root), conversation_id, expiry) == 'expired'
    assert totals(client)['summary'] == summary
    assert client.delete(f'{ROOT}/tasks/{task_id}').status_code == 200
    deleted = totals(client)
    assert deleted['summary'] == summary
    assert all(e['taskDeleted'] for e in deleted['events'])


def test_full_range_scoping_days_and_paging(files_env, monkeypatch):
    client, factory, _, identity = files_env
    task, _ = create(client)
    actor = identity[0]
    other = UserRecord(id=uuid4(), name='另一个操作者', role='designer', status='active', identity_source='development')
    with factory.begin() as session:
        session.add(other)
        session.get(UserRecord, actor).role = 'super_admin'
    initial = fact(actor, task, 'version_published')
    initial['occurred_at'] = datetime(2025, 1, 1, 15, 59, tzinfo=timezone.utc)
    modified = fact(actor, task, 'version_published')
    modified.update(kind='text_repair', operator_id=other.id, occurred_at=initial['occurred_at'] + timedelta(minutes=1))
    mock_facts(monkeypatch, [initial, modified, fact(actor, task, 'adopt'), fact(actor, task)])
    first, second = totals(client, '&pageSize=1'), totals(client, '&pageSize=1&page=2')
    assert first['summary'] == second['summary']
    assert first['summary']['totalGeneratedImages'] == 2
    assert first['summary']['generatedTasks'] == 1
    assert first['total'] == 2 and len(first['events']) == 1
    assert first['events'][0]['id'] != second['events'][0]['id']
    assert {r['date'] for r in first['rows']} == {'2025-01-01', '2025-01-02'}
    assert totals(client, '&from=2025-01-02&to=2025-01-02')['summary']['modifiedImages'] == 1
    assert totals(client, '&from=2030-01-01')['summary']['totalGeneratedImages'] == 0
    assert totals(client, f'&userId={other.id}')['summary']['initialImages'] == 0
    with factory.begin() as session:
        session.get(UserRecord, actor).role = 'designer'
    assert totals(client)['summary']['totalGeneratedImages'] == 1
    assert client.get(URL + f'?outputsOnly=true&userId={other.id}').status_code == 403


def test_unproven_history_remains_visible_as_unknown(files_env):
    client, factory, _, identity = files_env
    create(client, 1)
    with factory.begin() as session:
        item = session.scalar(select(ApiItem))
        session.add(ApiVersion(item_id=item.id, number=1, file_id=item.source_id,
            operator_id=identity[0], kind=None))
    report = totals(client)
    assert report['summary']['totalGeneratedImages'] == 0
    assert report['summary']['unverifiedVersions'] == 1
    assert report['events'] == [] and report['rows'] == []
    with factory.begin() as session:
        preserve(session)
    assert totals(client)['summary'] == report['summary']


def test_only_successful_outputs_count_and_all_api_edit_types():
    actor, task = uuid4(), str(uuid4())
    rows = []
    for kind in ('generation', 'image_edit', 'text_edit', 'text_repair', 'revision'):
        row = fact(actor, task, 'version_published')
        row['kind'] = kind
        rows.append(row)
    candidate = fact(actor, task, 'cli_candidate')
    candidate.update(channel='cli', kind='image_edit')
    rows.append(candidate)
    rows.extend(fact(actor, task, category) for category in ('api_request', 'cli_round', 'adopt', 'restore', 'task_created'))
    failed = fact(actor, task, 'version_published')
    failed['state'] = 'failed'
    rows.append(failed)
    summary = summarize(rows)
    assert (summary.initialImages, summary.modifiedImages, summary.totalGeneratedImages) == (1, 5, 6)
    assert summary.generatedTasks == 1


@pytest.mark.parametrize('query', ['generationType=unknown', 'outputsOnly=invalid'])
def test_new_query_validation(files_env, query):
    assert files_env[0].get(URL + '?' + query).status_code == 422


def test_record_page_sizes_keep_filter_and_cover_all_rows(files_env):
    client, factory, _, identity = files_env
    original_id, _ = create(client, 1)
    with factory.begin() as session:
        original = session.get(ApiTask, UUID(original_id))
        for index in range(56):
            session.add(ApiTask(owner_id=identity[0], operator_id=identity[0],
                name=f'分页验收{index:02}', prompt='local-only', material_id=original.material_id,
                parameters={}, state='succeeded'))
    url = ROOT + '/tasks?search=分页验收&status=succeeded'
    ids = set()
    for page in (1, 2, 3):
        response = client.get(url + f'&pageSize=20&page={page}')
        assert response.status_code == 200, response.text
        result = response.json()
        assert result['total'] == 56 and result['pageSize'] == 20
        assert len(result['items']) == (16 if page == 3 else 20)
        current = {t['id'] for t in result['items']}
        assert not ids & current
        ids |= current
    for size in (50, 100):
        response = client.get(url + f'&pageSize={size}&page=1')
        assert response.status_code == 200, response.text
        result = response.json()
        assert result['total'] == 56 and len(result['items']) == min(56, size)
        assert {t['id'] for t in result['items']} <= ids
