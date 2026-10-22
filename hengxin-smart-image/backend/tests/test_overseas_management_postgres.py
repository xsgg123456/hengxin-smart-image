from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from app.core.config import get_settings
from app.overseas.auth.models import Member
from app.overseas.execution import claims
from app.overseas.execution.models import ExecutionGate, Job
from app.overseas.execution.queue import enqueue, lock_gate
from app.overseas.management import settings
from app.overseas.management.models import Audit, Settings
from app.overseas.management.schemas import SettingsPatch
from overseas_installed_helpers import install_sample, enable_sample
from app.overseas.plans.snapshot import SKILL
from test_overseas_members_postgres import pg_factory, member
from test_overseas_concurrency import execution, add
from test_overseas_configuration import configure_overseas


@pytest.fixture(autouse=True)
def configured(monkeypatch, tmp_path):
    configure_overseas(monkeypatch)
    get_settings.cache_clear()
    get_settings().local_skill_root = str(tmp_path / 'skills')
    (tmp_path / 'skills').mkdir()
    yield
    get_settings.cache_clear()


def body(version=1, **updates):
    return SettingsPatch(version=version, paused=False, concurrency=2, timeoutSeconds=120,
        defaults={'analysis': None, 'generation': None, 'revision': None}, **updates)


def test_settings_concurrent_first_write_one_version_one_audit(pg_factory):
    actor = member(pg_factory)
    with pg_factory.begin() as session:
        session.add(ExecutionGate(id=1))
    barrier = Barrier(2)
    def save(_):
        with pg_factory() as session:
            user = session.get(Member, actor)
            barrier.wait(timeout=8)
            try:
                settings.save(session, user, body())
                return 200
            except HTTPException as error:
                return error.status_code
    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(save, range(2))) == [200, 409]
    with pg_factory() as session:
        assert session.get(Settings, 1).version == 2
        assert session.scalar(select(func.count()).select_from(Audit)) == 1


def test_lower_capacity_pause_and_unknown_keeps_slot(execution):
    factory, task = execution
    ids = [add(factory, task, str(i)) for i in range(4)]
    assert claims.claim(factory, ids[0]) and claims.claim(factory, ids[1])
    with factory.begin() as session:
        session.add(Settings(id=1, version=1, values={'concurrency': 1}))
        session.get(Job, ids[0]).status = 'uncertain'
    assert claims.claim(factory, ids[2]) is None
    with factory.begin() as session:
        session.get(Job, ids[1]).process_exited = True
        claims.end(session, session.get(Job, ids[1]), 'failed')
    assert claims.claim(factory, ids[2]) is None
    with factory.begin() as session:
        session.get(Job, ids[0]).process_exited = True
        claims.end(session, session.get(Job, ids[0]), 'failed')
        session.get(Settings, 1).values = {'concurrency': 1, 'paused': True}
    assert claims.claim(factory, ids[2]) is None
    with factory.begin() as session:
        session.get(Settings, 1).values = {'concurrency': 1, 'paused': False}
    assert claims.claim(factory, ids[2])
    assert claims.claim(factory, ids[3]) is None


def test_freeze_waits_for_atomic_skill_and_settings_update(pg_factory):
    actor = member(pg_factory)
    with pg_factory.begin() as session:
        session.add(ExecutionGate(id=1))
    with pg_factory() as session:
        item = install_sample('bound', content='one')
        enable_sample(pg_factory, 'bound')
        patch = SettingsPatch(**{**body().model_dump(), 'defaults': {
            'analysis': item['id'], 'generation': None, 'revision': None}})
        settings.save(session, session.get(Member, actor), patch)
    entered = Event()
    def freeze():
        with pg_factory.begin() as session:
            settings.values(session)  # Populate stale identity map before waiting.
            entered.set()
            return settings.freeze(session, 'analysis', SKILL)
    with pg_factory() as session:
        lock_gate(session)
        row = session.get(Settings, 1)
        row.values = {**row.values, 'timeoutSeconds': 180}
        with ThreadPoolExecutor(1) as pool:
            future = pool.submit(freeze)
            assert entered.wait(timeout=8)
            session.commit()
            assert future.result(timeout=8)['runtime'] == {'timeoutSeconds': 180}
