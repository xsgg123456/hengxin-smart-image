"""The new runner shares CLI capacity and never reruns an expired invocation."""
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import select

from app.capacity.models import CapacityGate, CapacityReservation
from app.db.timestamps import utcnow
from app.models import Job, Outbox
from app.modules.domestic_studio import runtime, turn_service
from app.modules.domestic_studio.turn_models import Turn
from app.overseas.studio.schemas import Send
from test_domestic_studio_bindings_pg import database
from test_domestic_turns_pg import bind, context


def test_other_domestic_cli_job_counts_and_expired_lease_does_not_rerun(context, database, monkeypatch):
    factory, catalog, skill, actor, _, channel, _ = context
    CapacityGate.__table__.create(database)
    CapacityReservation.__table__.create(database)
    monkeypatch.setattr(runtime, 'get_settings', lambda: SimpleNamespace(generation_concurrency=1, job_lease_seconds=30))
    other = uuid4()
    with factory.begin() as session:
        bind(session, skill['id'])
        turn_service.send(session, actor, 'camera', channel, Send(text='设计要求'), 'send', catalog)
        job_id = session.scalar(select(Turn.job_id))
        session.add(Job(id=other, kind='api_cli_edit', idempotency_key='other', payload_hash='f' * 64,
                        value='other', status='running'))
    assert runtime.claim(factory, job_id) is None
    with factory.begin() as session:
        session.get(Job, other).status = 'succeeded'
    token = runtime.claim(factory, job_id)
    assert token is not None
    with factory.begin() as session:
        job = session.get(Job, job_id)
        assert job.status == 'running' and job.execution_count == 1
        job.lease_until = utcnow() - timedelta(seconds=1)
    runtime.sweep(factory)
    assert runtime.claim(factory, job_id) is None
    with factory() as session:
        job = session.get(Job, job_id)
        assert job.status == 'uncertain' and job.execution_count == 1
        assert session.get(Outbox, job_id).completed_at is not None
