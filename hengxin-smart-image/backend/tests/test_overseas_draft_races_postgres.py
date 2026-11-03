"""Deterministic PG lock interleavings for completion versus clear/submission."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Event
from time import monotonic, sleep
from uuid import UUID
import pytest
from fastapi import HTTPException
from sqlalchemy import func, select, text
from app.overseas.auth.models import Member
from app.overseas.drafts import queue, service
from app.overseas.drafts.models import DraftImport, DraftMaterial, RequirementDraft
from app.overseas.drafts.schemas import SaveDraft, VersionBody
from app.overseas.tasks.models import Task
from app.overseas.tasks.schemas import CreateTask
from app.overseas.tasks.service import create_task
from test_overseas_draft_postgres import seed, add_job
from test_overseas_draft_reads_postgres import get, record
from test_overseas_members_postgres import pg_factory


class ObservedFactory:
    def __init__(self, factory, *, hold_commit=False):
        self.factory, self.hold_commit = factory, hold_commit
        self.started, self.completed, self.release = Event(), Event(), Event()
        self.pid = None

    @contextmanager
    def begin(self):
        with self.factory.begin() as session:
            self.pid = session.scalar(text('SELECT pg_backend_pid()'))
            self.started.set()
            yield session
            self.completed.set()
            if self.hold_commit:
                assert self.release.wait(10)


def blocked_by(factory, waiter, holder):
    deadline = monotonic() + 5
    with factory() as session:
        while holder not in session.scalar(text('SELECT pg_blocking_pids(:pid)'), {'pid': waiter}):
            assert monotonic() < deadline, 'expected PostgreSQL row-lock wait did not occur'
            sleep(0.01)


def test_clear_holds_lock_then_late_completion_is_fenced(pg_factory):
    actor_id, draft = seed(pg_factory)
    add_job(pg_factory, actor_id)
    job = queue.claim(pg_factory)
    observed = ObservedFactory(pg_factory)
    with pg_factory() as holder, ThreadPoolExecutor(1) as pool:
        actor = holder.get(Member, actor_id)
        service.owned(holder, actor)
        holder_pid = holder.scalar(text('SELECT pg_backend_pid()'))
        pending = pool.submit(queue.complete, observed, job, record())
        try:
            assert observed.started.wait(5)
            blocked_by(pg_factory, observed.pid, holder_pid)
            cleared = service.clear(holder, actor, VersionBody(version=draft['version']))
        finally:
            holder.rollback()
        assert pending.result(timeout=10) is False
    assert cleared['id'] != draft['id'] and cleared['materials'] == cleared['imports'] == []
    with pg_factory() as session:
        assert session.get(DraftImport, job.id).state == 'cancelled'
        assert session.scalar(select(func.count()).select_from(DraftMaterial)) == 0


def test_completion_holds_lock_then_clear_removes_link(pg_factory):
    actor_id, draft = seed(pg_factory)
    add_job(pg_factory, actor_id)
    job = queue.claim(pg_factory)
    observed = ObservedFactory(pg_factory, hold_commit=True)
    clear_started, clear_pid = Event(), []
    def clear():
        with pg_factory() as session:
            clear_pid.append(session.scalar(text('SELECT pg_backend_pid()')))
            clear_started.set()
            return service.clear(session, session.get(Member, actor_id), VersionBody(version=draft['version']))
    with ThreadPoolExecutor(2) as pool:
        completion = pool.submit(queue.complete, observed, job, record())
        try:
            assert observed.completed.wait(5)
            clearing = pool.submit(clear)
            assert clear_started.wait(5)
            blocked_by(pg_factory, clear_pid[0], observed.pid)
        finally:
            observed.release.set()
        assert completion.result(timeout=10) is True
        cleared = clearing.result(timeout=10)
    assert cleared['id'] != draft['id'] and cleared['materials'] == cleared['imports'] == []
    assert queue.complete(pg_factory, job, record()) is False
    with pg_factory() as session:
        assert session.get(DraftImport, job.id).state == 'cancelled'
        assert session.scalar(select(func.count()).select_from(DraftMaterial)) == 0


def test_completion_races_submit_stale_attachments_are_rejected_then_retry_consumes(pg_factory):
    actor_id, draft = seed(pg_factory)
    fields = dict(name='图需', productName='灯具', brand='OUTON', platform='Amazon',
        language='en', market='美国', skus=[{'code': 'A'}], designerId=str(actor_id))
    with pg_factory() as session:
        draft = service.save(session, session.get(Member, actor_id), SaveDraft(
            version=draft['version'], fields=fields))
    add_job(pg_factory, actor_id)
    job = queue.claim(pg_factory)
    observed = ObservedFactory(pg_factory, hold_commit=True)
    submit_started, submit_pid = Event(), []
    stale = CreateTask(**fields, draftId=UUID(draft['id']), draftVersion=draft['version'])
    def submit():
        with pg_factory() as session:
            submit_pid.append(session.scalar(text('SELECT pg_backend_pid()')))
            submit_started.set()
            try:
                create_task(session, session.get(Member, actor_id), stale, draft['submitKey'])
            except HTTPException as error:
                return error.status_code, error.detail
            pytest.fail('stale attachment set was accepted')
    with ThreadPoolExecutor(2) as pool:
        completion = pool.submit(queue.complete, observed, job, record())
        try:
            assert observed.completed.wait(5)
            submitting = pool.submit(submit)
            assert submit_started.wait(5)
            blocked_by(pg_factory, submit_pid[0], observed.pid)
        finally:
            observed.release.set()
        assert completion.result(timeout=10) is True
        status, detail = submitting.result(timeout=10)
    assert status == 409 and '附件' in detail
    with pg_factory() as session:
        assert session.scalar(select(func.count()).select_from(Task)) == 0
    current = get(pg_factory, actor_id)
    body = CreateTask(**current['fields'], draftId=UUID(current['id']),
        draftVersion=current['version'], materialIds=[UUID(item['id']) for item in current['materials']])
    with pg_factory() as session:
        created, is_new = create_task(session, session.get(Member, actor_id), body, current['submitKey'])
    assert is_new and queue.complete(pg_factory, job, record()) is False
    consumed = get(pg_factory, actor_id)
    assert consumed['id'] != current['id'] and consumed['materials'] == consumed['imports'] == []
    assert consumed['lastSubmittedTaskId'] == created['id']
    with pg_factory() as session:
        replay, is_new = create_task(session, session.get(Member, actor_id), body, current['submitKey'])
        assert not is_new and replay['id'] == created['id']
