from fastapi import APIRouter
from fastapi.responses import JSONResponse
from minio import Minio
from redis import Redis
from sqlalchemy import text
from urllib3 import PoolManager, Timeout

from app.core.config import get_settings
from app.db.session import get_engine

router = APIRouter(tags=["health"])


def dependency_checks():
    settings = get_settings()
    checks = {}
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SET LOCAL statement_timeout = '2000ms'"))
            conn.execute(text("SELECT 1"))
            conn.execute(text("SELECT id FROM job_outbox LIMIT 0"))
        checks["postgresql"] = "up"
    except Exception:
        checks["postgresql"] = "down"
    try:
        with Redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2) as client:
            client.ping()
        checks["redis"] = "up"
    except Exception:
        checks["redis"] = "down"
    try:
        client = Minio(
            settings.minio_endpoint, access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key, secure=settings.minio_secure,
            http_client=PoolManager(timeout=Timeout(connect=2, read=2), retries=False),
        )
        client.list_buckets()
        checks["minio"] = "up"
    except Exception:
        checks["minio"] = "down"
    return checks


@router.get("/health/live")
def live():
    return {"status": "ok"}


@router.get("/health/ready")
def ready():
    checks = dependency_checks()
    ready = all(value == "up" for value in checks.values())
    return JSONResponse(status_code=200 if ready else 503,
                        content={"status": "ready" if ready else "unavailable", "checks": checks})
