"""Real row locks ensure one decision enters studio without starting AI work."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID
import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from app.overseas.auth.models import Member
from app.overseas.execution.models import ExecutionGate, Job, JobOutbox
from app.overseas.plans.models import Plan
from app.overseas.tasks.models import Task, TaskEvent, RequirementsReview as Review
from app.overseas.tasks.requirements import review, resubmit
from app.overseas.tasks.schemas import RequirementsReview, ResubmitTask
from app.overseas.materials.service import submit
from app.overseas.materials.schemas import SubmitMaterials
from test_overseas_members_postgres import pg_factory, member
from test_overseas_tasks_postgres import create
from test_overseas_materials_postgres import ready


@pytest.fixture
def pending_pg(pg_factory):
    factory = pg_factory
    operator, designer = member(factory, 'operator'), member(factory, 'designer')
    with factory.begin() as session:
        session.add(ExecutionGate(id=1))
    task = create(factory, operator, designer, 'new')[1]
    material, _ = ready(factory, operator)
    with factory() as session:
        submit(session, session.get(Member, operator), UUID(task['id']),
               SubmitMaterials(version=1, materialIds=[material]), 'submit')
    return factory, operator, designer, UUID(task['id']), material


@pytest.mark.parametrize('same_key', [True, False])
def test_concurrent_review_opens_studio_exactly_once_without_job(pending_pg, same_key):
    factory, _, designer, task_id, _ = pending_pg
    barrier = Barrier(2)
    def act(index):
        with factory() as session:
            actor = session.get(Member, designer)
            barrier.wait(timeout=8)
            try:
                result = review(session, actor, task_id, RequirementsReview(version=2, decision='approve'),
                                'same' if same_key else str(index))
                assert result['status'] == 'studio' and result['version'] == 3
                return 200
            except HTTPException as exc:
                return exc.status_code
    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(act, (1, 2))) == ([200, 200] if same_key else [200, 409])
    with factory() as session:
        for model in (Job, JobOutbox, Plan):
            assert session.scalar(select(func.count()).select_from(model)) == 0
        assert session.scalar(select(func.count()).select_from(Review)) == 1
        decision = session.scalar(select(Review))
        assert decision.task_id == task_id and decision.actor_id == designer
        assert decision.decision == 'approve' and decision.version == 2
        assert session.scalar(select(func.count()).select_from(TaskEvent).where(
            TaskEvent.task_id == task_id, TaskEvent.kind == 'task.requirements_approved')) == 1
        task = session.get(Task, task_id)
        assert task.version == 3 and task.status == 'studio'
        assert task.workflow == 'studio' and task.requirements_approved


def test_concurrent_resubmit_preserves_one_submission(pending_pg):
    factory, operator, designer, task_id, material = pending_pg
    with factory() as session:
        review(session, session.get(Member, designer), task_id,
               RequirementsReview(version=2, decision='reject', comment='补充'), 'reject')
    with factory() as session:
        task = session.get(Task, task_id)
        body = ResubmitTask(name=task.name, productName=task.product_name, brand=task.brand,
            platform=task.platform, market=task.market, remarks='修订', skus=[{'code': 'NEW'}],
            designerId=designer, materialIds=[material], version=3)
    barrier = Barrier(2)
    def act(index):
        with factory() as session:
            actor = session.get(Member, operator)
            barrier.wait(timeout=8)
            try:
                resubmit(session, actor, task_id, body, str(index))
                return 200
            except HTTPException as exc:
                return exc.status_code
    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(act, (1, 2))) == [200, 409]
    with factory() as session:
        task = session.get(Task, task_id)
        assert task.version == 4 and task.status == 'pending_review' and not task.requirements_approved
        assert session.scalar(select(func.count()).select_from(Job)) == 0
