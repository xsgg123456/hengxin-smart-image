"""Previously fenced failures recover through the ordinary hourly PostgreSQL scan."""
from datetime import timedelta
import os

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.execution.cleanup_paths import CleanupSafetyError
from app.modules.api_image_edits.models import ApiFile, ApiItem, ApiTask, ApiVersion
from app.retention import paths
from app.retention.observability_models import RetentionRecord, RetentionTotals
from app.retention.state import entry
from app.retention.worker import run_once
from test_api_cli_concurrency import pg_edit
from test_retention_concurrency import prepared_api, workspace, Store
from test_cleanup_retention_safety import tools_in


@pytest.mark.skipif(os.name != 'posix', reason='production tool links on real Linux')
def test_hourly_scan_recovers_existing_link_failure_without_manual_state_reset(pg_edit, tmp_path, monkeypatch):
    factory, _, task_id, item_id = pg_edit
    now, identifier, _, _, _ = prepared_api(pg_edit)
    directory = workspace(tmp_path, identifier)
    tools_in(directory / 'home' / '.codex')
    settings, store = get_settings(), Store()
    monkeypatch.setattr(settings, 'cli_retention_enabled', True)
    monkeypatch.setattr(settings, 'codex_execution_root', str(tmp_path))
    original = paths.clean

    def legacy_reject(*args, **kwargs):
        raise CleanupSafetyError('UNEXPECTED_LINK')

    monkeypatch.setattr(paths, 'clean', legacy_reject)
    assert run_once(factory, store, settings, now)['resources'][0]['status'] == 'retry'
    with factory() as session:
        row = entry(session, 'api_cli', identifier)
        activity = row.last_activity_at
        assert row.status == 'expire_pending' and row.next_cleanup_at == now + timedelta(hours=1)
        assert session.scalar(select(RetentionRecord)).result == 'retry'
    monkeypatch.setattr(paths, 'clean', original)
    assert run_once(factory, store, settings, now + timedelta(minutes=59))['resources'] == []
    assert directory.exists()
    outcome = run_once(factory, store, settings, now + timedelta(hours=1))
    assert outcome['resources'][0]['status'] == 'expired' and outcome['objectsRemoved'] == 1
    assert not directory.exists()
    assert run_once(factory, store, settings, now + timedelta(hours=2))['resources'] == []
    with factory() as session:
        row = entry(session, 'api_cli', identifier)
        assert row.last_activity_at == activity and row.counters == {'turns': 1, 'calls': 2}
        records = session.scalars(select(RetentionRecord)).all()
        assert len(records) == 1 and records[0].counted and records[0].result == 'complete'
        assert session.get(RetentionTotals, 'api_cli').history_total == 1
        item, task = session.get(ApiItem, item_id), session.get(ApiTask, task_id)
        assert all(session.get(ApiFile, key) for key in (item.source_id, item.result_id, task.material_id))
        assert len(session.scalars(select(ApiVersion)).all()) == 1
    assert len(store.removed) == 1
