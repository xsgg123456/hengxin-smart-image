"""Run the HTTP record contract against the existing isolated PostgreSQL schema."""
import pytest
from fastapi.testclient import TestClient

from app.db.session import get_session
from app.main import app
from app.modules.auth.dependencies import get_identity_id
from app.storage.minio_store import get_store
from test_api_image_execution_pg import pg_api, enabled_api
import test_api_image_records as records

pytestmark = pytest.mark.integration


@pytest.fixture
def pg_files_env(pg_api):
    factory, user, _, store = pg_api
    identity = [user.id]
    def database():
        with factory() as session:
            yield session
    app.dependency_overrides[get_session] = database
    app.dependency_overrides[get_identity_id] = lambda: identity[0]
    app.dependency_overrides[get_store] = lambda: store
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client, factory, store, identity
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize('contract', [
    records.test_default_owner_all_other_and_identity_switch,
    records.test_creators_include_disabled_history_current_and_use_ids,
    records.test_beijing_dates_inclusive_start_exclusive_next_day,
    records.test_stats_match_full_filter_not_page_and_deleted_excluded,
    records.test_empty_no_items_and_stable_order,
    records.test_aggregate_does_not_load_task_or_item_payloads,
], ids=lambda contract: contract.__name__)
def test_record_contract_postgres(pg_files_env, contract):
    contract(pg_files_env)
