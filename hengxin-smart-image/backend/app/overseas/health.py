"""Read-only readiness against overseas resources, without administrative credentials."""
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from redis import Redis
from sqlalchemy import text
from urllib3 import PoolManager, Timeout

from app.core.config import get_settings
from app.db.session import get_engine
from app.overseas.db import SCHEMA_REVISION
from app.storage.minio_store import MinioStore

router = APIRouter(prefix='/api/overseas/v1/health', tags=['health'])
SCHEMA_VERSION = SCHEMA_REVISION


def dependency_checks():
    settings = get_settings()
    checks = {}
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SET LOCAL statement_timeout = '2000ms'"))
            versions = connection.execute(
                text('SELECT version_num FROM overseas_alembic_version')
            ).scalars().all()
            if versions != [SCHEMA_VERSION]:
                raise RuntimeError('Overseas schema is not current')
        checks['postgresql'] = 'up'
    except Exception:
        checks['postgresql'] = 'down'
    try:
        with Redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2) as client:
            client.ping()
        checks['redis'] = 'up'
    except Exception:
        checks['redis'] = 'down'
    http = PoolManager(timeout=Timeout(connect=2, read=2), retries=False)
    try:
        store = MinioStore(http_client=http)
        store.ensure_private(settings.minio_bucket, create_missing=False)
        checks['minio'] = 'up'
    except Exception:
        checks['minio'] = 'down'
    finally:
        http.clear()
    return checks


@router.get('/live')
def live():
    return {'status': 'ok'}


@router.get('/ready')
def ready():
    checks = dependency_checks()
    available = all(value == 'up' for value in checks.values())
    return JSONResponse(status_code=200 if available else 503, content={
        'status': 'ready' if available else 'unavailable', 'checks': checks,
    })
