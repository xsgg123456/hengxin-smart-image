"""Actual row-lock ordering; never substitute SQLite for concurrency evidence."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event

from fastapi import HTTPException
from sqlalchemy import func, select

from app.core.config import get_settings
from app.overseas.auth.models import Member
from app.overseas.execution.models import ExecutionGate
from app.overseas.execution.queue import lock_gate
from app.overseas.management import skills
from app.overseas.management.models import Audit, InstalledSkillAvailability
from app.overseas.management.schemas import SkillPatch
from app.overseas.management.settings import freeze_selected
from overseas_installed_helpers import install_sample, enable_sample
from test_overseas_management_postgres import configured
from test_overseas_members_postgres import pg_factory, member


def test_concurrent_owner_toggles_have_one_commit_one_conflict(pg_factory):
    actor = member(pg_factory)
    get_settings().skill_toggle_owner_id = actor
    item = install_sample()
    with pg_factory.begin() as session:
        session.add(ExecutionGate(id=1))
    barrier = Barrier(2)

    def toggle(_):
        with pg_factory() as session:
            user = session.get(Member, actor)
            barrier.wait(timeout=8)
            try:
                skills.set_availability(session, user, item['id'], SkillPatch(enabled=True, version=1))
                return 200
            except HTTPException as error:
                return error.status_code

    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(toggle, range(2))) == [200, 409]
    with pg_factory() as session:
        state = session.get(InstalledSkillAvailability, 'sample')
        assert (state.enabled, state.version) == (True, 2)
        assert session.scalar(select(func.count()).select_from(Audit)) == 1


def test_freeze_reloads_stale_availability_after_waiting_for_gate(pg_factory):
    item = install_sample()
    enable_sample(pg_factory)
    with pg_factory.begin() as session:
        session.add(ExecutionGate(id=1))
    entered = Event()

    def freeze():
        with pg_factory.begin() as session:
            cached = session.get(InstalledSkillAvailability, 'sample')
            assert cached.enabled
            entered.set()
            try:
                freeze_selected(session, item['id'])
                return 200
            except HTTPException as error:
                return error.status_code

    with pg_factory() as session:
        lock_gate(session)
        row = session.get(InstalledSkillAvailability, 'sample')
        row.enabled, row.version = False, 2
        with ThreadPoolExecutor(1) as pool:
            future = pool.submit(freeze)
            assert entered.wait(timeout=8)
            session.commit()
            assert future.result(timeout=8) == 422
