"""Run the same real HTTP/frozen-input contracts against isolated PostgreSQL."""
import pytest
from app.db.session import get_session
from app.overseas.execution.models import ExecutionGate
from test_overseas_auth import overseas as sqlite_overseas
from test_overseas_members_postgres import pg_factory
from test_overseas_materials import materials
from test_overseas_studio import studio
from test_studio_image_edits import editable
from test_studio_image_references import (
    referenced,
    test_http_freeze_context_files_prompt_and_public_history as assert_reference_roundtrip,
    test_history_keeps_sent_metadata_and_files_after_material_hidden as assert_history_frozen,
    test_old_edit_fingerprint_replays_with_explicit_empty_references as assert_legacy_retry,
)


@pytest.fixture
def overseas(sqlite_overseas, pg_factory):
    client, _, assertion = sqlite_overseas

    def database():
        with pg_factory() as session:
            yield session

    client.app.dependency_overrides[get_session] = database
    with pg_factory.begin() as session:
        session.add(ExecutionGate(id=1))
    yield client, pg_factory, assertion


def test_postgres_reference_roundtrip(referenced, tmp_path):
    assert_reference_roundtrip(referenced, tmp_path)


def test_postgres_history_frozen(referenced):
    assert_history_frozen(referenced)


def test_postgres_legacy_retry(editable):
    assert_legacy_retry(editable)
