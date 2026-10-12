"""Overseas ASGI entry; liveness does not certify dependency readiness."""
from fastapi import FastAPI

from app.core.config import get_business_context, get_settings
from app.errors import register_errors
from app.http_timing import HttpTimingMiddleware

if get_business_context() != 'overseas':
    raise RuntimeError('Overseas entry requires HX_BUSINESS_CONTEXT=overseas')

get_settings()
from app.overseas.health import router  # noqa: E402 - validate context before loading resources
from app.overseas.auth.router import router as auth_router
from app.overseas.members.router import router as members_router
from app.overseas.tasks.router import router as tasks_router
from app.overseas.materials.router import router as materials_router

app = FastAPI(title='恒鑫智图 · 海外业务 API', version='0.1.0')
register_errors(app)
app.add_middleware(HttpTimingMiddleware)


app.include_router(router)
app.include_router(auth_router)
app.include_router(members_router)
app.include_router(tasks_router)
app.include_router(materials_router)

from app.overseas.execution.router import router as execution_router
app.include_router(execution_router)

from app.overseas.plans.router import router as plans_router
app.include_router(plans_router)

from app.overseas.pictures.router import router as pictures_router
from app.overseas.archives.router import router as archives_router
app.include_router(pictures_router)
app.include_router(archives_router)
from app.overseas.management.router import router as management_router
app.include_router(management_router)
