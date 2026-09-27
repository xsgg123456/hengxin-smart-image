"""Disposable real PostgreSQL process contention, migrations and MinIO recovery."""
from io import BytesIO
import json
import multiprocessing as mp
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
from uuid import uuid4

from alembic import command
from alembic.config import Config
from PIL import Image
from sqlalchemy import MetaData, Table, select

from app.core.config import get_settings
from app.db.session import get_engine, session_factory
from app.capacity.admission import reserve, pending_bytes
from app.capacity.models import CapacityGate, CapacityReservation
from app.capacity.observation import sample
from app.models import utcnow
from app.resource_models import UserRecord
from app.modules.api_image_edits.models import ApiFile, ApiItem, ApiTask
from app.modules.api_image_edits.execution import execute_next
from app.modules.api_image_edits.files import new_record
from app.modules.api_image_edits.schemas import CreateTask
from app.modules.api_image_edits.service import submit
from app.modules.api_image_edits.relay import RelayResult
from app.modules.files.validation import validate_image
from app.storage.minio_store import get_store

MIB = 1024 * 1024


def contender(start, pipe, kind):
    start.wait(20)
    try:
        identity = uuid4()
        with session_factory().begin() as session:
            result = reserve(session, identity, kind, identity, 40 * MIB)
        pipe.send(result)
    finally:
        pipe.close()
        get_engine().dispose()


def contention(factory):
    with factory.begin() as session:
        row = session.get(CapacityGate, 1)
        row.enabled, row.free_bytes, row.floor_bytes = True, 500 * MIB, 100 * MIB
        row.api_bytes = row.cli_bytes = 400 * MIB
        row.volumes, row.sample_at = {'isolated': 'simulated 400 MiB headroom'}, utcnow()
    context = mp.get_context('spawn')
    start, workers = context.Event(), []
    try:
        for index in range(12):
            left, right = context.Pipe()
            process = context.Process(target=contender, args=(start, right, 'api' if index % 2 else 'cli'))
            process.start(); right.close()
            workers.append((process, left))
        start.set()
        wins = []
        for process, pipe in workers:
            assert pipe.poll(60), 'capacity contender hung'
            wins.append(pipe.recv())
        assert sum(wins) == 1, wins
    finally:
        for process, pipe in workers:
            process.join(10)
            if process.is_alive(): process.kill(); process.join(5)
            pipe.close()
        assert all(process.exitcode == 0 for process, _ in workers)
    with factory() as session:
        assert pending_bytes(session) == 400 * MIB
        winner = session.scalar(select(CapacityReservation))
        identity, kind, owner = winner.id, winner.kind, winner.owner_id
    # A completely new engine/session still sees and reuses the paid promise.
    get_engine().dispose()
    with factory.begin() as session:
        session.get(CapacityGate, 1).free_bytes = 0
        assert reserve(session, identity, kind, owner, 40 * MIB)
        assert pending_bytes(session) == 400 * MIB
    try:
        with factory.begin() as session:
            row = session.get(CapacityGate, 1)
            row.free_bytes = 2000 * MIB
            assert reserve(session, uuid4(), 'api', uuid4(), 40 * MIB)
            raise RuntimeError('rollback')
    except RuntimeError:
        pass
    with factory() as session:
        assert pending_bytes(session) == 400 * MIB
    return {'processes': 12, 'winners': 1, 'restart_retained': True, 'rollback_retained': True}


def main():
    settings = get_settings()
    assert settings.app_env == 'test' and settings.database_url.endswith('/media_test')
    assert settings.minio_bucket.startswith('media-test-')
    for attempt in range(40):
        try:
            with get_engine().connect(): break
        except Exception:
            if attempt == 39: raise
            time.sleep(.3)
    config = Config('alembic.ini')
    command.upgrade(config, '0017')
    factory = session_factory()
    buffer = BytesIO()
    Image.new('RGB', (16, 16), 'blue').save(buffer, format='PNG')
    data = buffer.getvalue()
    image = validate_image(SimpleNamespace(file=BytesIO(data), filename='source.png', content_type='image/png'))
    store = get_store()
    with factory() as session:
        user = UserRecord(name='isolated capacity test', role='super_admin', status='active', identity_source='development')
        session.add(user); session.commit()
        # Seed the old schema using its old contract, not today's publishing hook.
        file = new_record(user.id, image)
        session.add(file); session.commit()
        store.put(file, image.data)
        file.status = 'ready'; session.commit()
        task = ApiTask(owner_id=user.id, operator_id=user.id, name='legacy receipt', prompt='fixture',
                       material_id=file.id, parameters={}, state='failed', events=[])
        session.add(task); session.commit()
        legacy_id = uuid4()
        old_items = Table('api_image_items', MetaData(), autoload_with=get_engine())
        session.execute(old_items.insert().values(id=legacy_id, task_id=task.id, source_id=file.id,
            position=1, state='failed', result_bytes=data, created_at=utcnow(), updated_at=utcnow()))
        session.commit()
    command.upgrade(config, 'head')
    command.upgrade(config, 'head')
    from app.modules.files.variants import backfill, ImageVariants
    assert backfill(factory) == 1
    with factory() as session:
        assert session.get(ImageVariants, ('api-image-edits', file.id)).source_checksum == image.checksum
    with factory() as session:
        legacy = session.get(ApiItem, legacy_id)
        assert legacy.result_bytes == data and legacy.capacity_cycle_id is None and legacy.staging_file_id is None
        assert not session.get(CapacityGate, 1).enabled
    result = {'migration_preserved_legacy_receipt': True, **contention(factory)}
    with factory.begin() as session:
        row = session.get(CapacityGate, 1)
        row.free_bytes, row.api_bytes, row.sample_at = 4000 * MIB, 60 * MIB, utcnow()
    with factory() as session:
        task_id = submit(session, user, CreateTask(name='capacity recovery', prompt='fixture',
                          originalFileIds=[file.id], materialFileId=file.id), 'capacity-fixture')
    class Client:
        calls = 0
        def generate(self, *args):
            self.calls += 1
            return RelayResult(image_bytes=data)
    class AmbiguousStore:
        failed = False
        def __getattr__(self, name): return getattr(store, name)
        def put(self, record, body):
            store.put(record, body)
            if not self.failed:
                self.failed = True
                raise OSError('real MinIO PUT succeeded; response lost')
    client, ambiguous = Client(), AmbiguousStore()
    assert execute_next(factory, ambiguous, client)
    with factory.begin() as session:
        item = session.scalar(select(ApiItem).where(ApiItem.task_id == task_id))
        staging, cycle = item.staging_file_id, item.capacity_cycle_id
        assert staging and session.get(CapacityReservation, cycle).state == 'held'
        item.next_attempt_at = None
        session.get(CapacityGate, 1).free_bytes = 0
    assert execute_next(factory, ambiguous, client)
    with factory() as session:
        item = session.scalar(select(ApiItem).where(ApiItem.task_id == task_id))
        assert item.state == 'succeeded' and item.result_id == staging and client.calls == 1
        assert session.get(CapacityReservation, cycle).state == 'published'
        assert store.stat(session.get(ApiFile, staging)) == len(data)
        assert len(list(store.client.list_objects(settings.minio_bucket, prefix=f'api-image-edits/{staging}'))) == 1
    # Real local filesystem sampling, not a claim to observe production MinIO/PG mounts.
    with tempfile.TemporaryDirectory(prefix='capacity-probe-') as folder:
        paths = {role: str(Path(folder).resolve()) for role in ('execution', 'objects', 'database')}
        with factory.begin() as session:
            session.get(CapacityGate, 1).volumes = {}
            observation = sample(session, paths)
            assert json.loads(json.dumps(observation))['pendingBytes'] == 400 * MIB
            assert session.get(CapacityReservation, cycle).state == 'accounted'
            assert pending_bytes(session) == 400 * MIB  # Unknown winner never released.
    result.update(real_minio_ambiguous_put_reused=True, model_stub_calls=client.calls,
                  physical_sample_accounted_only_published=True)
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
