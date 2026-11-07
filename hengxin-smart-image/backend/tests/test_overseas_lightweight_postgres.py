"""Run the new read paths against an isolated PostgreSQL schema as well as SQLite."""
import pytest

import test_overseas_auth as auth
from test_overseas_members_postgres import pg_factory  # noqa: F401
from test_overseas_task_deletion import deletion  # noqa: F401
from test_overseas_studio import studio  # noqa: F401
from test_overseas_materials import materials  # noqa: F401
from test_overseas_lightweight import (  # noqa: F401
    test_actual_send_replay_cancel_and_new_request_are_counted,
    test_people_counts_requests_not_claims_and_preserves_scopes,
    test_task_group_and_assignee_apply_before_count_and_pagination,
)
from test_overseas_archive_audit import test_actor_snapshot_multiple_confirmations_and_replay  # noqa: F401


@pytest.fixture
def overseas(monkeypatch, tmp_path, pg_factory):
    # The shared fixture sets up authentication and the HTTP app; only its isolated
    # database engine changes. pg_factory rejects non-test databases and owns cleanup.
    monkeypatch.setattr(auth, 'create_engine', lambda *args, **kwargs: pg_factory.kw['bind'])
    yield from auth.overseas.__wrapped__(monkeypatch, tmp_path)
