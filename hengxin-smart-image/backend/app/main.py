from fastapi import FastAPI

from app.core.config import get_settings
from app.contracts.router import router as contracts_router
from app.contracts.business import ApiErrorBody
from app.errors import register_errors
from app.health import router as health_router
from app.jobs import router as jobs_router

get_settings()  # Refuse unsafe environment configuration before serving requests.
app = FastAPI(title="恒信智能影像 API", version="0.1.0", responses={
    422: {"model": ApiErrorBody, "description": "请求参数不符合接口约定"},
    500: {"model": ApiErrorBody, "description": "服务异常"},
})
register_errors(app)
app.include_router(health_router, prefix="/api/v1")
app.include_router(jobs_router, prefix="/api/v1")
app.include_router(contracts_router, prefix="/api/v1")
