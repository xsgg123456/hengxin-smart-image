import hashlib
import json
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.contracts.business import ApiErrorBody
from app.db.session import get_session
from app.models import Job, Outbox, utcnow

router = APIRouter(tags=["internal-test-jobs"], responses={
    404: {"model": ApiErrorBody, "description": "测试入口关闭或作业不存在"},
    409: {"model": ApiErrorBody, "description": "幂等键与已有请求内容冲突"},
})


class TestJobInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str = Field(min_length=1, max_length=4096)
    delaySeconds: int = Field(default=0, ge=0, le=30)


class JobResponse(BaseModel):
    jobId: UUID
    status: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    result: str | None
    executionCount: int


def require_test_jobs():
    settings = get_settings()
    if settings.app_env not in ("development", "test") or not settings.enable_test_jobs:
        raise HTTPException(404, "接口不存在")


def job_response(job: Job):
    return JobResponse(jobId=job.id, status=job.status, result=job.result,
                       executionCount=job.execution_count)


def create_job(session: Session, key: str, payload: TestJobInput):
    fingerprint = hashlib.sha256(json.dumps(payload.model_dump(), sort_keys=True).encode()).hexdigest()
    job_id = uuid4()
    # The unique key arbitrates concurrent retries. Job and outbox commit together.
    with session.begin():
        inserted = session.scalar(insert(Job).values(
            id=job_id, idempotency_key=key, payload_hash=fingerprint,
            value=payload.value, delay_seconds=payload.delaySeconds,
            status="queued", execution_count=0, created_at=utcnow(),
        ).on_conflict_do_nothing(index_elements=[Job.idempotency_key]).returning(Job.id))
        if inserted:
            session.add(Outbox(job_id=job_id))
        job = session.scalar(select(Job).where(Job.idempotency_key == key))
        if job.payload_hash != fingerprint:
            raise HTTPException(409, "同一幂等键不能提交不同内容")
    return job


@router.post("/internal/test-jobs", status_code=202, response_model=JobResponse,
             dependencies=[Depends(require_test_jobs)])
def submit_test_job(
    payload: TestJobInput,
    idempotency_key: Annotated[str, Header(min_length=1, max_length=128, pattern=r"^[!-~]+$")],
    session: Session = Depends(get_session),
):
    return job_response(create_job(session, idempotency_key, payload))


@router.get("/internal/test-jobs/{job_id}", response_model=JobResponse,
            dependencies=[Depends(require_test_jobs)])
def read_test_job(job_id: UUID, session: Session = Depends(get_session)):
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "作业不存在")
    return job_response(job)
