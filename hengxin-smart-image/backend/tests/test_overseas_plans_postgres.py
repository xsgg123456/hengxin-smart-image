"""Real PostgreSQL contention and atomic plan publication/confirmation."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID
import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from app.overseas.auth.models import Member
from app.overseas.execution import claims
from app.overseas.execution.models import ExecutionGate, Job
from app.overseas.plans import service
from app.overseas.plans.analysis import HANDLER
from app.overseas.plans.models import Plan
from app.overseas.plans.schemas import AnalysisRequest, ConfirmRequest
from app.overseas.materials import service as materials_service
from app.overseas.materials.schemas import SubmitMaterials
from app.overseas.tasks.models import Task
from app.overseas.tasks.requirements import review
from app.overseas.tasks.schemas import RequirementsReview
from test_overseas_members_postgres import pg_factory, member
from test_overseas_tasks_postgres import create
from test_overseas_materials_postgres import ready


@pytest.fixture
def plan_pg(pg_factory):
    factory = pg_factory
    operator, designer = member(factory, 'operator'), member(factory, 'designer')
    with factory.begin() as session:
        session.add(ExecutionGate(id=1))
    task = create(factory, operator, designer, 'new')[1]
    material, _ = ready(factory, operator)
    with factory() as session:
        materials_service.submit(session, session.get(Member, operator), UUID(task['id']),
            SubmitMaterials(version=1, materialIds=[material]), 'submit')
    with factory() as session:
        review(session, session.get(Member, designer), UUID(task['id']),
               RequirementsReview(version=2, decision='approve'), 'review')
    with factory() as session:
        plan = session.scalar(select(Plan))
        job = session.get(Job, plan.job_id)
        content = {'skus': [{'code': sku['code'], 'pictures': [{'title': 'title', 'description': 'full',
            'prompt': 'full prompt', 'width': 1024, 'height': 1024}]} for sku in job.payload['task']['skus']]}
        identity = plan.job_id
        plan_id = plan.id
    token = claims.claim(factory, identity)
    with factory.begin() as session:
        session.get(Job, identity).process_exited = True
    assert claims.finish(factory, identity, token, 'succeeded', content, publish=HANDLER.publish)
    return factory, designer, UUID(task['id']), plan_id


@pytest.mark.parametrize('same_key', [True, False])
def test_concurrent_confirmation_creates_one_group(plan_pg, same_key):
    factory, designer, task, plan = plan_pg
    barrier = Barrier(2)
    def confirm(index):
        with factory() as session:
            barrier.wait(timeout=8)
            try:
                service.confirm(session, session.get(Member, designer), task, plan,
                    ConfirmRequest(version=4), 'same' if same_key else str(index))
                return 200
            except HTTPException as exc:
                return exc.status_code
    with ThreadPoolExecutor(2) as pool:
        result = list(pool.map(confirm, [1, 2]))
    assert sorted(result) == ([200, 200] if same_key else [200, 409])
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Job).where(Job.kind == 'generation')) == 2
        assert session.get(Task, task).version == 5


def test_concurrent_reanalysis_one_version_and_rollback(plan_pg, monkeypatch):
    factory, designer, task, plan = plan_pg
    original = service.enqueue
    calls = 0
    def fail_second(*args, **kwargs):
        nonlocal calls
        job = original(*args, **kwargs)
        calls += 1
        if calls == 2:
            raise RuntimeError('second generation failed')
        return job
    monkeypatch.setattr(service, 'enqueue', fail_second)
    with factory() as session, pytest.raises(RuntimeError, match='second generation'):
        service.confirm(session, session.get(Member, designer), task, plan, ConfirmRequest(version=4), 'atomic')
    with factory() as session:
        assert session.get(Plan, plan).status == 'ready'
        assert session.get(Task, task).status == 'plan'
        assert session.scalar(select(func.count()).select_from(Job).where(Job.kind == 'generation')) == 0
    monkeypatch.setattr(service, 'enqueue', original)
    barrier = Barrier(2)
    def reanalyze(index):
        with factory() as session:
            barrier.wait(timeout=8)
            try:
                service.analyze(session, session.get(Member, designer), task,
                    AnalysisRequest(version=4, feedback='Change'), str(index))
                return 200
            except HTTPException as exc:
                return exc.status_code
    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(reanalyze, [1, 2])) == [200, 409]
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Plan)) == 2
