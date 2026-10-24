"""Runs only under the installed overseas worker account; JSON input/output.

No CLI/model invocation. The release driver owns private recovery files and the
HTTP closure; backend locks enforce actor authority, paused gate and task state.
"""
import json
from pathlib import Path
import sys
from uuid import UUID


def execution_facts(session, job):
    from app.overseas.execution.models import JobOutbox
    outbox = session.get(JobOutbox, job.id)
    return dict(jobId=str(job.id), executionCount=job.execution_count,
        startedAt=job.started_at.isoformat() if job.started_at else None,
        completedAt=job.completed_at.isoformat() if job.completed_at else None,
        outboxCompletedAt=outbox.completed_at.isoformat() if outbox and outbox.completed_at else None)


def authorize(session, body):
    from app.overseas.auth.models import Member
    from app.overseas.tasks.service import lock_actor
    actor = session.get(Member, UUID(body['actor_id']))
    assert actor is not None, 'Maintenance actor missing'
    lock_actor(session, actor, 'settings.manage')


def drained(session):
    from sqlalchemy import select, or_
    from app.overseas.execution.models import Job, TERMINAL
    assert session.scalar(select(Job.id).where(or_(Job.status.not_in(TERMINAL),
        (Job.process_id.is_not(None) & ~Job.process_exited))).limit(1)) is None, 'Execution has not drained'


def verified(factory, body, store):
    from hashlib import sha256
    from sqlalchemy import select
    from app.overseas.studio.image_recovery import _locked
    from app.overseas.studio.models import Picture, ConversationDeletion
    from app.overseas.tasks.models import ExecutionObject
    from app.overseas.management.models import Audit
    from app.overseas.studio.files import read
    with factory.begin() as session:
        task, turn, channel, job = _locked(session, UUID(body['turn_id']), UUID(body['actor_id']))
        assert not session.get(ConversationDeletion, channel.id), 'Conversation deletion exists'
        assert turn.delivery_error is None and job.result.get('deliveryStatus') == {
            'state': 'complete', 'expected': 8, 'saved': 8}, 'Delivery is not complete'
        rows = list(session.scalars(select(Picture).where(Picture.turn_id == turn.id).order_by(Picture.id)))
        assert len(rows) == 8 and {row.source_path: row.checksum for row in rows} == body['expected_checksums'], 'Stored image selection mismatch'
        objects = []
        for row in rows:
            assert row.task_id == task.id, 'Picture task mismatch'
            ledger = session.scalar(select(ExecutionObject).where(ExecutionObject.bucket == row.bucket,
                ExecutionObject.object_key == row.object_key))
            assert ledger and ledger.job_id == job.id and ledger.task_id == task.id, 'Image ledger mismatch'
            # The same reader serves browser preview/download. It reads actual
            # stored bytes and checks size/hash, never trusting object metadata.
            data = read(store, row)
            assert sha256(data).hexdigest() == body['expected_checksums'][row.source_path], 'Stored original bytes mismatch'
            objects.append(dict(id=str(row.id), path=row.source_path, checksum=row.checksum,
                size=len(data), bucket=row.bucket, key=row.object_key, ledgerId=str(ledger.id)))
        audits = list(session.scalars(select(Audit).where(Audit.target == str(job.id),
            Audit.action == 'studio.delivery_repair').order_by(Audit.id)))
        return dict(execution=execution_facts(session, job), objects=objects,
            jobVersion=job.version, jobResult=job.result,
            audits=[dict(id=str(row.id), before=row.before, after=row.after) for row in audits])


def execute(packet, factory, store=None):
    from app.overseas.db import require_overseas_context
    from app.overseas.execution.queue import lock_gate
    from app.overseas.execution.models import Job
    from app.overseas.studio.models import Turn
    from app.overseas.studio.delivery_repair import repair
    from app.storage.minio_store import get_store
    require_overseas_context()
    body, action = packet['request'], packet['action']
    if action in ('inspect', 'pause', 'restore', 'hold'):
        with factory.begin() as session:
            authorize(session, body)
            gate = lock_gate(session)
            if action == 'hold':
                # Closing admission is safe even if collection is still active.
                gate.paused = True
                return {'paused': True}
            drained(session)
            if action == 'inspect':
                turn = session.get(Turn, UUID(body['turn_id']))
                assert turn is not None, 'Turn missing'
                job = session.get(Job, turn.job_id)
                return dict(paused=gate.paused, execution=execution_facts(session, job))
            original = packet['original_paused']
            assert type(original) is bool, 'Unknown original gate state'
            assert gate.paused == (original if action == 'pause' else True), 'Execution gate drift'
            gate.paused = True if action == 'pause' else original
            return dict(paused=gate.paused)
    if action in ('dry-run', 'apply', 'repeat'):
        return repair(factory, body['turn_id'], body['actor_id'], body['expected_sha256'],
                      body['expected_checksums'], apply=action != 'dry-run', store=store)
    if action in ('verify', 'verify-repeat'):
        return verified(factory, body, store or get_store())
    raise ValueError('Unknown repair action')


def main():
    if sys.flags.optimize:
        raise RuntimeError('Python -O disables repair safety assertions')
    import app
    from app.overseas.db import session_factory
    assert Path(app.__file__).resolve().parent.parent == Path.cwd(), 'Repair imported a different installation'
    packet = json.load(sys.stdin)
    print(json.dumps(execute(packet, session_factory())), flush=True)


if __name__ == '__main__':
    main()
