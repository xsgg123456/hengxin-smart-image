"""Local QA server: disposable PostgreSQL schema, memory files, fake upstream only."""
import json
import os
from datetime import timedelta
from pathlib import Path
import sys
import time
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "hengxin-smart-image/backend"
sys.path[:0] = [str(BACKEND), str(BACKEND / "tests")]
database_url = os.environ["API_IMAGE_TEST_DATABASE_URL"]
from sqlalchemy.engine import make_url

assert make_url(database_url).database.endswith("_test"), "A dedicated *_test database is required"
assert make_url(database_url).host in {"127.0.0.1", "localhost"}, "Local QA database only"
os.environ.update(
    APP_ENV="test", HX_BUSINESS_CONTEXT="domestic", ENABLE_DEV_IDENTITY="false",
    DATABASE_URL=database_url, MINIO_ACCESS_KEY="test-access-key",
    MINIO_SECRET_KEY="test-secret-key", API_IMAGE_ENABLED="true",
    API_IMAGE_API_KEY="isolated-test-only-key",
)
from sqlalchemy import create_engine, text, select
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from fastapi.staticfiles import StaticFiles
from app.main import app
from app.models import Base, utcnow
from app.db.session import get_session
from app.modules.auth.dependencies import get_identity_id
from app.resource_models import UserRecord
from app.storage.minio_store import get_store
from files_helpers import MemoryStore, image_bytes
from test_api_image_domain import create
from app.modules.api_image_edits.execution import execute_next
from app.modules.api_image_edits.models import ApiItem
from app.modules.api_image_edits.relay import RelayError, RelayResult

OUTPUT = ROOT / "output/api-retry-simple-20261020"
OUTPUT.mkdir(parents=True, exist_ok=True)
SCHEMA = "qa_retry_simple_" + uuid4().hex
admin = create_engine(database_url)
with admin.begin() as connection:
    connection.execute(text("CREATE SCHEMA " + SCHEMA))
engine = create_engine(database_url, connect_args={"options": "-csearch_path=" + SCHEMA})
Base.metadata.create_all(engine)
factory = sessionmaker(engine, expire_on_commit=False)
store = MemoryStore()
with factory.begin() as session:
    user = UserRecord(id=uuid4(), name="重试隔离验收", role="operator",
                      status="active", identity_source="development")
    session.add(user)


def database():
    with factory() as session:
        yield session


app.dependency_overrides[get_session] = database
app.dependency_overrides[get_identity_id] = lambda: user.id
app.dependency_overrides[get_store] = lambda: store


class FakeClient:
    def __init__(self, fail=False):
        self.fail = fail

    def generate(self, *args):
        if self.fail:
            raise RelayError("uncertain", "TIMEOUT", "isolated unknown response")
        return RelayResult(image_bytes=image_bytes(), request_id="isolated-qa-result")


def seed():
    with TestClient(app) as client:
        task_id, _ = create(client, 3, key="qa-simple-browser")
        assert execute_next(factory, store, FakeClient())
        with factory.begin() as session:
            second = session.scalar(select(ApiItem).where(
                ApiItem.task_id == UUID(task_id), ApiItem.position == 2))
            second.attempts = 19
        time.sleep(5.2)
        assert execute_next(factory, store, FakeClient(fail=True))
        time.sleep(5.2)
        assert execute_next(factory, store, FakeClient(fail=True))
        with factory.begin() as session:
            third = session.scalar(select(ApiItem).where(
                ApiItem.task_id == UUID(task_id), ApiItem.position == 3))
            third.next_attempt_at = utcnow() + timedelta(minutes=10)
        response = client.get("/api/v1/api-image-edits/tasks/" + task_id)
        assert response.status_code == 200, response.text
        task = response.json()
        assert [item["state"] for item in task["items"]] == ["succeeded", "failed", "retry_wait"], task
        (OUTPUT / "live-fixture.json").write_text(json.dumps(
            {"schema": SCHEMA, "taskId": task_id, "initialTask": task},
            ensure_ascii=False, indent=2), encoding="utf-8")


@app.post("/__qa__/step")
def step():
    """Only this standalone loopback QA harness exposes fake-upstream progression."""
    return {"claimed": execute_next(factory, store, FakeClient())}


if __name__ == "__main__":
    import uvicorn
    try:
        seed()
        app.mount("/", StaticFiles(directory=BACKEND.parent / "frontend/dist", html=True))
        uvicorn.run(app, host="127.0.0.1", port=18924, log_level="warning")
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text("DROP SCHEMA " + SCHEMA + " CASCADE"))
        admin.dispose()
