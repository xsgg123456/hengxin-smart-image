"""Real PostgreSQL ordering between platform writes, toggles, and admission."""
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
from app.overseas.management.schemas import SkillPatch, SkillPlatformsPatch
from app.overseas.management.settings import freeze_selected
from overseas_installed_helpers import install_sample, enable_sample
from test_overseas_management_postgres import configured
from test_overseas_members_postgres import pg_factory, member


def test_parallel_platform_and_toggle_share_one_revision(pg_factory):
    admin, owner = member(pg_factory), member(pg_factory)
    get_settings().skill_toggle_owner_id = owner
    item = install_sample()
    with pg_factory.begin() as session:
        session.add(ExecutionGate(id=1))
    barrier = Barrier(2)

    def write(kind):
        with pg_factory() as session:
            actor = session.get(Member, admin if kind == 'platform' else owner)
            barrier.wait(timeout=8)
            try:
                if kind == 'platform':
                    skills.set_platforms(session, actor, SkillPlatformsPatch(items=[
                        dict(id=item['id'], platforms=['Amazon', 'Walmart'], version=1)]))
                else:
                    skills.set_availability(session, actor, item['id'], SkillPatch(enabled=True, version=1))
                return 200
            except HTTPException as error:
                return error.status_code

    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(write, ['platform', 'toggle'])) == [200, 409]
    with pg_factory() as session:
        row = session.get(InstalledSkillAvailability, item['name'])
        assert row.version == 2
        assert (row.enabled, row.platforms) in [(True, []), (False, ['Amazon', 'Walmart'])]
        assert session.scalar(select(func.count()).select_from(Audit)) == 1


def test_freeze_rechecks_platform_after_waiting_for_gate(pg_factory):
    item = install_sample()
    enable_sample(pg_factory)
    with pg_factory.begin() as session:
        session.add(ExecutionGate(id=1))
    entered = Event()

    def freeze():
        with pg_factory.begin() as session:
            cached = session.get(InstalledSkillAvailability, 'sample')
            assert cached.platforms == ['Amazon']
            entered.set()
            try:
                freeze_selected(session, item['id'], 'Amazon')
                return 200
            except HTTPException as error:
                return error.status_code

    with pg_factory() as session:
        lock_gate(session)
        row = session.get(InstalledSkillAvailability, 'sample')
        row.platforms, row.version = ['Walmart'], 2
        with ThreadPoolExecutor(1) as pool:
            future = pool.submit(freeze)
            assert entered.wait(timeout=8)
            session.commit()
            assert future.result(timeout=8) == 422


def test_overlapping_batches_never_partially_commit(pg_factory):
    admins = [member(pg_factory), member(pg_factory)]
    first, second = install_sample(), install_sample('second')
    with pg_factory.begin() as session:
        session.add(ExecutionGate(id=1))
    barrier = Barrier(2)

    def write(index):
        with pg_factory() as session:
            actor = session.get(Member, admins[index])
            barrier.wait(timeout=8)
            try:
                skills.set_platforms(session, actor, SkillPlatformsPatch(items=[
                    dict(id=item['id'], platforms=[['Amazon', 'Walmart'][index]], version=1)
                    for item in ([first, second] if index == 0 else [second, first])]))
                return 200
            except HTTPException as error:
                return error.status_code

    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(write, range(2))) == [200, 409]
    with pg_factory() as session:
        rows = session.scalars(select(InstalledSkillAvailability)).all()
        assert len(rows) == 2 and all(row.version == 2 for row in rows)
        assert rows[0].platforms == rows[1].platforms
        assert session.scalar(select(func.count()).select_from(Audit)) == 2
