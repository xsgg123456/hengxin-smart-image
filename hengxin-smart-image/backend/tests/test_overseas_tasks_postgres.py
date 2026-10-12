"""Actual PostgreSQL advisory/row locks and permission refresh under contention."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from time import monotonic, sleep
from uuid import UUID
import pytest
from fastapi import HTTPException
from sqlalchemy import delete, text
from app.overseas.auth.models import Member, MemberRole
from app.overseas.members import service as members
from app.overseas.tasks import service, assignment
from app.overseas.tasks.schemas import CreateTask, Assignment
from test_overseas_members_postgres import pg_factory, member
from test_overseas_tasks import payload, counts


def create(factory, actor_id, designer, key='same', barrier=None, name=None):
    with factory() as session:
        actor = session.get(Member, actor_id)
        data = payload(designer)
        if name:
            data['name'] = name
        if barrier:
            barrier.wait(timeout=8)
        try:
            result, created = service.create_task(session, actor, CreateTask(**data), key)
            return 201 if created else 200, result
        except HTTPException as exc:
            return exc.status_code, None


def assign(factory, actor_id, task, designer, key, barrier=None):
    with factory() as session:
        actor = session.get(Member, actor_id)
        if barrier:
            barrier.wait(timeout=8)
        try:
            return 200, assignment.assign(session, actor, UUID(task['id']),
                Assignment(designerId=designer, version=1), key)
        except HTTPException as exc:
            return exc.status_code, None


@pytest.mark.parametrize('different', [False, True])
def test_concurrent_same_key_create(pg_factory, different):
    actor, designer = member(pg_factory, 'operator'), member(pg_factory, 'designer')
    barrier = Barrier(2)
    with ThreadPoolExecutor(2) as pool:
        futures = [pool.submit(create, pg_factory, actor, designer, 'same', barrier,
                               'other' if i and different else None) for i in range(2)]
        assert sorted(f.result(timeout=15)[0] for f in futures) == ([201, 409] if different else [200, 201])
    assert counts(pg_factory) == [1, 2, 1, 1, 1]


def test_same_key_is_independent_per_actor(pg_factory):
    a, b = member(pg_factory, 'operator'), member(pg_factory, 'operator')
    designer = member(pg_factory, 'designer')
    barrier = Barrier(2)
    with ThreadPoolExecutor(2) as pool:
        futures = [pool.submit(create, pg_factory, actor, designer, 'same', barrier) for actor in (a, b)]
        assert [f.result(timeout=15)[0] for f in futures] == [201, 201]
    assert counts(pg_factory) == [2, 4, 2, 2, 2]


def test_concurrent_assignment_same_version(pg_factory):
    creator = member(pg_factory, 'operator')
    manager = member(pg_factory, 'design_manager')
    first, second, third = [member(pg_factory, 'designer') for _ in range(3)]
    _, task = create(pg_factory, creator, first)
    barrier = Barrier(2)
    with ThreadPoolExecutor(2) as pool:
        futures = [pool.submit(assign, pg_factory, manager, task, designer, str(i), barrier)
                   for i, designer in enumerate((second, third))]
        assert sorted(f.result(timeout=15)[0] for f in futures) == [200, 409]
    assert counts(pg_factory) == [1, 2, 2, 2, 2]


@pytest.mark.parametrize('operation', ['create', 'assignment'])
@pytest.mark.parametrize('target', ['actor', 'candidate'])
@pytest.mark.parametrize('disabled', [False, True])
def test_waiting_permission_changes_revalidated(pg_factory, monkeypatch, operation, target, disabled):
    creator = member(pg_factory, 'operator')
    actor = creator if operation == 'create' else member(pg_factory, 'design_manager')
    candidate = member(pg_factory, 'designer')
    task = create(pg_factory, creator, member(pg_factory, 'designer'), 'initial')[1] if operation == 'assignment' else None
    waiting = Event()
    original = members.lock_permissions

    def signal_wait(session):
        waiting.set()
        original(session)

    with pg_factory() as first:
        original(first)
        monkeypatch.setattr(members, 'lock_permissions', signal_wait)
        with ThreadPoolExecutor(1) as pool:
            future = (pool.submit(create, pg_factory, actor, candidate) if operation == 'create'
                      else pool.submit(assign, pg_factory, actor, task, candidate, 'wait'))
            assert waiting.wait(5)
            deadline = monotonic() + 5
            while not first.scalar(text("SELECT count(*) FROM pg_locks WHERE locktype='advisory' "
                                        'AND NOT granted AND objid=:key'),
                                   {'key': members.PERMISSION_LOCK & 0xFFFFFFFF}):
                assert monotonic() < deadline
                sleep(0.01)
            victim = actor if target == 'actor' else candidate
            if disabled:
                first.get(Member, victim).status = 'disabled'
            else:
                first.execute(delete(MemberRole).where(MemberRole.user_id == victim))
                first.add(MemberRole(user_id=victim, role='operator' if operation == 'assignment' or target == 'candidate' else 'designer'))
            first.commit()
            assert future.result(timeout=15)[0] == (403 if target == 'actor' else 422)
    assert counts(pg_factory) == ([1, 2, 1, 1, 1] if task else [0] * 5)
