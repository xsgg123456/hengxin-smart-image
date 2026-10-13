"""PostgreSQL task locks serialize review/rework and fence late publication."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
from uuid import UUID
import pytest
from fastapi import HTTPException
from sqlalchemy import select, func
from app.overseas.auth.models import Member
from app.overseas.execution import claims
from app.overseas.execution.models import Job
from app.overseas.plans import service as plans
from app.overseas.plans.schemas import ConfirmRequest
from app.overseas.pictures import review, revisions
from app.overseas.pictures.models import Picture, PictureVersion
from app.overseas.pictures.schemas import VersionRequest, RevisionRequest
from app.overseas.generation import delivery
from app.overseas.tasks.models import Task
from test_overseas_plans_postgres import plan_pg
from test_overseas_members_postgres import pg_factory
from test_overseas_pictures import generate
from test_overseas_materials import MemoryStore


@pytest.fixture
def picture_pg(plan_pg, monkeypatch, tmp_path):
    factory, actor, task, plan = plan_pg
    monkeypatch.setattr(delivery, 'get_store', lambda: store)
    store = MemoryStore()
    with factory() as session:
        plans.confirm(session, session.get(Member, actor), task, plan, ConfirmRequest(version=4), 'confirm')
    with factory() as session:
        jobs = session.scalars(select(Job.id).where(Job.kind == 'generation')).all()
    for job in jobs:
        generate(factory, job, tmp_path)
    with factory() as session:
        picture = session.scalar(select(Picture).where(Picture.task_id == task))
        return factory, actor, task, picture.id, session.get(Task, task).version


@pytest.mark.parametrize('same_key', [True, False])
def test_concurrent_revision_only_one_job(picture_pg, same_key):
    factory, actor, task, picture, task_version = picture_pg
    barrier = Barrier(2)
    def run(index):
        with factory() as session:
            # Populate stale identity map intentionally before competing task locks.
            session.get(Picture, picture)
            barrier.wait(timeout=8)
            try:
                revisions.revise(session, session.get(Member, actor), picture,
                    RevisionRequest(version=1, taskVersion=task_version, note='change', marks=[]),
                    'same' if same_key else str(index))
                return 200
            except HTTPException as error:
                return error.status_code
    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(run, [1, 2])) == ([200, 200] if same_key else [200, 409])
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Job).where(Job.kind == 'revision')) == 1
        assert session.get(Picture, picture).version == 1


def test_review_and_revision_same_task_version_only_one_wins(picture_pg):
    factory, actor, task, picture, task_version = picture_pg
    barrier = Barrier(2)
    def run(index):
        with factory() as session:
            barrier.wait(timeout=8)
            try:
                if index:
                    review.approve(session, session.get(Member, actor), picture,
                        VersionRequest(version=1, taskVersion=task_version), 'approve')
                else:
                    revisions.revise(session, session.get(Member, actor), picture,
                        RevisionRequest(version=1, taskVersion=task_version, note='change', marks=[]), 'revise')
                return 200
            except HTTPException as error:
                return error.status_code
    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(run, [0, 1])) == [200, 409]


def test_late_cancelled_delivery_cannot_publish(picture_pg, tmp_path):
    factory, actor, task, picture, task_version = picture_pg
    with factory() as session:
        revisions.revise(session, session.get(Member, actor), picture,
            RevisionRequest(version=1, taskVersion=task_version, note='change', marks=[]), 'revision')
    with factory() as session:
        job_id = session.scalar(select(Job.id).where(Job.kind == 'revision'))
    token = claims.claim(factory, job_id)
    with factory.begin() as session:
        job = session.get(Job, job_id)
        job.process_exited = True
        job.cancel_requested = True
    assert not claims.finish(factory, job_id, token, 'succeeded', {'images': []}, publish=delivery.HANDLER.publish)
    with factory() as session:
        assert session.get(Picture, picture).version == 1
        assert session.scalar(select(func.count()).select_from(PictureVersion).where(PictureVersion.picture_id == picture)) == 1


def test_failed_maximum_length_sku_retry_uses_bounded_request_target(plan_pg):
    from app.overseas.generation.service import retry
    from app.overseas.pictures.schemas import RetryRequest
    factory, actor, task, plan = plan_pg
    with factory() as session:
        plans.confirm(session, session.get(Member, actor), task, plan, ConfirmRequest(version=4), 'confirm')
    code = 'X' * 80
    with factory.begin() as session:
        picture = session.scalar(select(Picture).where(Picture.task_id == task))
        picture.sku = code
        job = session.get(Job, picture.job_id)
        job.payload = {**job.payload, 'sku': {**job.payload['sku'], 'code': code}}
        claims.end(session, job, 'failed', error=True)
    with factory() as session:
        result = retry(session, session.get(Member, actor), task, RetryRequest(version=5, sku=code), 'retry')
        assert result['version'] == 6
