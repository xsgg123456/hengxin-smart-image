"""Real database contention: assignment and deletion preserve the last valid owner."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from app.overseas.auth.models import Member
from app.overseas.archives.models import Archive
from app.overseas.tasks import assignment, deletion, cleanup
from app.overseas.tasks.models import Task
from app.overseas.tasks.schemas import Assignment, DeleteTask
from test_overseas_tasks import overseas
from test_overseas_members_postgres import pg_factory, member
from test_overseas_deletion_postgres import ready, save


@pytest.mark.parametrize('assign_first', [True, False])
def test_assignment_delete_serialize_on_parent_task(ready, monkeypatch, assign_first):
    factory, store, (admin, task, _) = ready
    assert save(ready) == 200
    next_designer = member(factory, 'designer')
    other_admin = member(factory)
    with factory() as session:
        version = session.get(Task, task).version
    entered, release = Event(), Event()
    module, name = (assignment, 'record_change') if assign_first else (deletion, 'stopping')
    original = getattr(module, name)

    def held(*args, **kwargs):
        entered.set()
        assert release.wait(timeout=8)
        return original(*args, **kwargs)

    monkeypatch.setattr(module, name, held)

    def act(is_assign, expected_version=version):
        with factory() as session:
            try:
                if is_assign:
                    assignment.assign(session, session.get(Member, admin), task,
                        Assignment(designerId=next_designer, version=expected_version), 'assign')
                else:
                    deletion.request(session, session.get(Member, other_admin), task,
                        DeleteTask(version=expected_version, confirmationName='待删除任务'))
                return 200
            except HTTPException as exc:
                return exc.status_code

    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(act, assign_first)
        assert entered.wait(timeout=8)
        second = pool.submit(act, not assign_first)
        release.set()
        assert first.result(timeout=15) == 200
        assert second.result(timeout=15) == 409
    if assign_first:
        assert act(False, version + 1) == 200
    assert cleanup.cleanup_once(factory, store) == 1
    with factory() as session:
        archive = session.scalar(select(Archive))
        assert session.get(Task, task) is None and archive.task_id is None
        assert archive.designer_id == (next_designer if assign_first else admin)
