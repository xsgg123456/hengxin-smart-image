from fastapi import FastAPI
from contextlib import asynccontextmanager
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.contracts.router import router as contracts_router
from app.contracts.business import ApiErrorBody
from app.errors import register_errors
from app.health import router as health_router
from app.jobs import router as jobs_router
from app.modules.auth.dev_identity import seed_dev_identity
from app.modules.auth.router import router as auth_router
from app.modules.files.router import router as files_router
from app.modules.files.downloads import router as downloads_router
from app.modules.templates.router import router as templates_router
from app.modules.tasks.router import router as tasks_router
from app.modules.revisions.router import router as revisions_router
from app.modules.archives.router import router as archives_router
from app.modules.skills.router import router as skills_router


@asynccontextmanager
async def lifespan(app):
    await run_in_threadpool(seed_dev_identity)
    yield

get_settings()  # Refuse unsafe environment configuration before serving requests.
app = FastAPI(title="恒信智能影像 API", version="0.1.0", lifespan=lifespan, responses={
    422: {"model": ApiErrorBody, "description": "请求参数不符合接口约定"},
    500: {"model": ApiErrorBody, "description": "服务异常"},
})
register_errors(app)
app.include_router(health_router, prefix="/api/v1")
app.include_router(jobs_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(files_router, prefix="/api/v1")
app.include_router(downloads_router, prefix="/api/v1")
app.include_router(templates_router, prefix="/api/v1")
app.include_router(skills_router, prefix="/api/v1")
app.include_router(tasks_router, prefix="/api/v1")
app.include_router(revisions_router, prefix="/api/v1")
app.include_router(archives_router, prefix="/api/v1")
app.include_router(contracts_router, prefix="/api/v1")
