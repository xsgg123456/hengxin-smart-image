"""Actual task locks serialize hide/restore and concurrent same-content uploads."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
import pytest
from sqlalchemy import select, func
from app.overseas.auth.models import Member
from app.overseas.studio import files, material_list, queries
from app.overseas.studio.models import MaterialVisibility
from test_overseas_deletion_postgres import ready
from test_overseas_members_postgres import pg_factory, member
from test_overseas_tasks import overseas


def upload(ready, actor=None):
    factory, store, (owner, task, _) = ready
    with factory() as session:
        return files.upload(session, store, session.get(Member, actor or owner), task, b'same', 'same.txt')


def remove(ready, identity, actor=None):
    factory, _, (owner, task, _) = ready
    with factory() as session:
        return material_list.remove(session, session.get(Member, actor or owner), task, identity)


def test_concurrent_identical_uploads_have_one_visible_group(ready):
    factory, _, (actor, task, _) = ready
    other = member(factory)
    barrier = Barrier(2)
    def add(person):
        barrier.wait(timeout=5)
        return upload(ready, person)
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(add, [actor, other]))
    assert sorted(row['materialState'] for row in results) == ['added', 'existing']
    assert len({row['id'] for row in results}) == 2
    with factory() as session:
        assert len(queries.view(session, session.get(Member, actor), task)['materials']) == 1


@pytest.mark.parametrize('hide_first', [True, False])
def test_hide_upload_contention_obeys_task_lock_order(ready, monkeypatch, hide_first):
    factory, _, (actor, task, _) = ready
    other = member(factory)
    existing = upload(ready)
    entered, release = Event(), Event()
    original = material_list.visibility
    calls = []
    def hold(*args):
        calls.append(1)
        if len(calls) == 1:
            entered.set()
            assert release.wait(timeout=8)
        return original(*args)
    monkeypatch.setattr(material_list, 'visibility', hold)
    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(remove, ready, existing['id']) if hide_first else pool.submit(upload, ready)
        assert entered.wait(timeout=8)
        second = pool.submit(upload, ready, other) if hide_first else pool.submit(remove, ready, existing['id'], other)
        release.set()
        first_result, second_result = first.result(timeout=15), second.result(timeout=15)
    uploaded = second_result if hide_first else first_result
    assert uploaded['materialState'] == ('restored' if hide_first else 'existing')
    with factory() as session:
        assert len(queries.view(session, session.get(Member, actor), task)['materials']) == int(hide_first)
        assert session.scalar(select(func.count()).select_from(MaterialVisibility)) == 1


def test_concurrent_duplicate_removes_are_idempotent(ready):
    factory, _, (actor, _, _) = ready
    other = member(factory)
    existing = upload(ready)
    barrier = Barrier(2)
    def hide(person):
        barrier.wait(timeout=5)
        return remove(ready, existing['id'], person)
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(hide, [actor, other]))
    assert all(result['materials'] == [] for result in results)
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(MaterialVisibility)) == 1
