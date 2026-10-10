"""Opt-in PostgreSQL fact backfill concurrency, each test owns a disposable schema."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from sqlalchemy import delete, select
from app.modules.api_image_edits.service import submit
from app.modules.management.api_stats.models import ApiUsageFact
from app.modules.management.api_stats.backfill import preserve
from app.modules.management.api_stats.projection import read_facts
from test_api_image_execution_pg import pg_api
from test_api_image_domain import enabled_api

pytestmark = pytest.mark.integration


def test_parallel_backfill_is_exactly_once(pg_api):
    factory, user, payload, _ = pg_api
    with factory() as session:
        submit(session, user, payload, 'fact-concurrency')
    with factory.begin() as session:
        session.execute(delete(ApiUsageFact))
    barrier = Barrier(4)
    def backfill(_):
        barrier.wait()
        with factory.begin() as session:
            return preserve(session)
    with ThreadPoolExecutor(max_workers=4) as pool:
        counts = list(pool.map(backfill, range(4)))
    assert sum(counts) == 1
    with factory.begin() as session:
        assert preserve(session) == 0
        assert len(session.scalars(select(ApiUsageFact)).all()) == 1
        assert len(read_facts(session)) == 1
