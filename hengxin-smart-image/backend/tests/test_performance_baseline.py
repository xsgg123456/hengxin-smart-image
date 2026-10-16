"""Run with pytest -s to save comparable JSON lines from entirely isolated data.

No external storage, real worker, model or production database is contacted.
Small generated fixture images test accounting, not production visual quality.
History sizes deliberately expose current cost without enshrining it as a budget.
"""
import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.modules.api_image_edits.models import ApiItem, ApiTask, ApiVersion
from files_helpers import files_env
from performance_samples import image_budget, sample
from test_api_image_domain import ROOT, create, enabled_api


def emit(name, rows, **dimensions):
    result = {
        'schema': 1, 'dataset': name, 'dimensions': dimensions,
        'environment': 'SQLite memory / in-process ASGI / MemoryStore',
        'scope': 'includes HTTP authorization; excludes network and browser; not p95',
        'samples': rows,
    }
    print('PERFORMANCE_BASELINE ' + json.dumps(result, ensure_ascii=False, sort_keys=True))




@pytest.mark.parametrize('history', [1, 8])
def test_api_history_cost_baseline(files_env, history):
    client, factory, _, identity = files_env
    fixed_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    identifiers = [create(client, count=2, key=f'baseline-{i}')[0] for i in range(9)]
    with factory.begin() as session:
        for identifier in identifiers:
            task = session.get(ApiTask, UUID(identifier))
            task.state, task.created_at = 'succeeded', fixed_time
            task.started_at = task.completed_at = fixed_time
            for item in session.scalars(select(ApiItem).where(ApiItem.task_id == task.id)):
                item.state, item.result_id, item.current_version = 'succeeded', item.source_id, history
                for number in range(1, history + 1):
                    session.add(ApiVersion(id=uuid4(), item_id=item.id, number=number,
                        file_id=item.source_id, operator_id=identity[0],
                        text='保留原始内容与历史意见。' * 30,
                        created_at=fixed_time, updated_at=fixed_time))
    measurements = []
    for _ in range(3):
        response, row = sample(client, ROOT + '/tasks?view=summary&pageSize=20')
        data = response.json()
        assert data['total'] == 9 and len(data['items']) == 9
        row['row_count'] = len(data['items'])
        # This is an inventory, not an assertion that future summaries carry history.
        row['embedded_versions'] = sum(len(item.get('versions', []))
            for task in data['items'] for item in task.get('items', []))
        measurements.append(row)
    pictures = [task['cover'] if 'cover' in task else task['items'][0]['source'] for task in data['items']]
    measurements.append({'visible_component_images': image_budget(client, pictures)})
    _, detail = sample(client, ROOT + '/tasks/' + identifiers[0])
    measurements.append({'detail': detail})
    emit('api-history-v1', measurements, tasks=9, items_per_task=2, versions_per_item=history)
