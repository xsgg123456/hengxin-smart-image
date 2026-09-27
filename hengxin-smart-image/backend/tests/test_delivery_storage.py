from io import BytesIO
from uuid import uuid4

import pytest
from fastapi import UploadFile
from sqlalchemy import select

from app.execution.delivery_storage import (
    DeliveryOwnershipLost, DeliveryStorageConflict, store_delivery,
)
from app.modules.files.validation import validate_image
from app.resource_models import FileRecord
from files_helpers import files_env, image_bytes


class RetryStore:
    def __init__(self):
        self.objects, self.calls, self.fail = {}, 0, False

    def put(self, record, data):
        self.calls += 1
        self.objects[record.object_key] = data
        if self.fail:
            raise OSError('ambiguous object write')

    def remove(self, record):
        pytest.fail('Delivery recovery must never remove possibly successful objects')


@pytest.fixture
def delivery(files_env):
    image = validate_image(UploadFile(BytesIO(image_bytes()), filename='final.png'))
    return (files_env[1], RetryStore(), files_env[3][0], uuid4(), [image], lambda: True)


def records(factory):
    with factory() as session:
        return list(session.scalars(select(FileRecord)))


def test_repeated_delivery_and_identical_slots(delivery):
    args = list(delivery)
    args[4] *= 2
    ids = store_delivery(*args)
    assert len(set(ids)) == 2
    assert store_delivery(*args) == ids
    assert args[1].calls == 2
    assert len(records(args[0])) == 2


def test_ambiguous_put_retry_uses_same_id(delivery):
    delivery[1].fail = True
    with pytest.raises(OSError):
        store_delivery(*delivery)
    first = records(delivery[0])[0]
    assert first.status == 'staging'
    delivery[1].fail = False
    assert store_delivery(*delivery) == [first.id]
    assert len(records(delivery[0])) == len(delivery[1].objects) == 1


@pytest.mark.parametrize('phase', [1, 2])
@pytest.mark.parametrize('ambiguous', [False, True])
def test_database_failure_recovers_without_duplicates(delivery, monkeypatch, phase, ambiguous):
    factory = delivery[0]
    original = factory.class_.commit
    calls = 0
    def failing_commit(session):
        nonlocal calls
        calls += 1
        if calls == phase:
            if ambiguous:
                original(session)
            raise OSError('injected database acknowledgement failure')
        return original(session)
    with monkeypatch.context() as patch:
        patch.setattr(factory.class_, 'commit', failing_commit)
        with pytest.raises(OSError):
            store_delivery(*delivery)
    ids = store_delivery(*delivery)
    assert store_delivery(*delivery) == ids
    assert len(records(factory)) == len(delivery[1].objects) == 1


@pytest.mark.parametrize('damage', ['owner', 'deleted', 'metadata'])
def test_existing_identity_cannot_be_repurposed(delivery, damage):
    ids = store_delivery(*delivery)
    with delivery[0].begin() as session:
        record = session.get(FileRecord, ids[0])
        if damage == 'owner':
            record.owner_id = uuid4()
        elif damage == 'deleted':
            from app.models import utcnow
            record.deleted_at = utcnow()
        else:
            record.checksum = '0' * 64
    with pytest.raises(DeliveryStorageConflict):
        store_delivery(*delivery)


def test_ownership_loss_after_put_does_not_mark_ready(delivery):
    args = list(delivery)
    args[5] = lambda: args[1].calls == 0
    with pytest.raises(DeliveryOwnershipLost):
        store_delivery(*args)
    assert records(args[0])[0].status == 'staging'
    assert len(args[1].objects) == 1


def test_failed_record_can_resume(delivery):
    ids = store_delivery(*delivery)
    with delivery[0].begin() as session:
        session.get(FileRecord, ids[0]).status = 'failed'
    assert store_delivery(*delivery) == ids
