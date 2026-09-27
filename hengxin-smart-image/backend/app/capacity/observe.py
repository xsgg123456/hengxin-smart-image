"""Local maintenance command: python -m app.capacity.observe --help (never auto-enable)."""
import argparse
import json
import time
from uuid import uuid4

from sqlalchemy import func, select

from app.db.session import session_factory
from app.core.config import get_settings
from app.models import Job
from app.modules.tasks.models import ExecutionGate, RoundRecord, TaskRecord, ResultSlotRecord
from app.modules.tasks.attempts import ExecutionAttempt
from app.modules.api_image_edits.models import ApiItem
from app.modules.api_image_edits.state import channel
from .admission import gate, reserve, pending_bytes
from .observation import sample

MIB = 1024 * 1024


def adopt_legacy(session):
    # Failed does not prove no paid output. Keep every potential CLI delivery;
    # do not inspect/delete arbitrary model workspace files during activation.
    rounds = session.scalars(select(RoundRecord).join(TaskRecord).where(
        TaskRecord.execution_source == 'cli', RoundRecord.status == 'failed',
        select(ExecutionAttempt.id).where(ExecutionAttempt.round_id == RoundRecord.id).exists()))
    count = 0
    for row in rounds:
        slots = 1 if row.target is not None else session.scalar(select(func.count()).select_from(
            ResultSlotRecord).where(ResultSlotRecord.task_id == row.task_id))
        if not reserve(session, row.id, 'cli', row.id, max(1, slots) * 20 * MIB):
            raise ValueError('Insufficient capacity for legacy CLI delivery debt; activation rolled back')
        count += 1
    for item in session.scalars(select(ApiItem).where(
            ApiItem.result_url.is_not(None) | ApiItem.result_bytes.is_not(None))):
        identity = item.capacity_cycle_id or uuid4()
        if not reserve(session, identity, 'api', item.id, 60 * MIB):
            raise ValueError('Insufficient capacity for legacy API receipt debt; activation rolled back')
        item.capacity_cycle_id = identity
        count += 1
    return count


def enable(session, paths, floor_bytes, api_bytes, cli_bytes):
    # Same direction as both claimers: business gates first, capacity last.
    if session.scalar(select(ExecutionGate).where(ExecutionGate.id == 1).with_for_update()) is None:
        raise ValueError('CLI execution gate missing')
    channel(session)
    policy = gate(session)
    if policy.enabled:
        raise ValueError('Already enabled; changing envelopes requires a separately reviewed drain procedure')
    cli_active = session.scalar(select(func.count()).select_from(Job).where(
        Job.kind == 'generation', Job.status.in_(['running', 'collecting', 'cancelling', 'uncertain'])))
    api_active = session.scalar(select(func.count()).select_from(ApiItem).where(
        ApiItem.state.in_(['running', 'collecting', 'uncertain'])))
    if cli_active or api_active:
        raise ValueError('Drain both channels and resolve legacy paid receipts before enabling')
    if floor_bytes <= 0 or api_bytes < 60 * MIB or cli_bytes < 400 * MIB:
        raise ValueError('Explicit measured envelopes required: API >=60 MiB, CLI >=400 MiB, positive safety floor')
    policy.floor_bytes, policy.api_bytes, policy.cli_bytes = floor_bytes, api_bytes, cli_bytes
    result = sample(session, paths)
    if policy.free_bytes - floor_bytes < max(api_bytes, cli_bytes):
        raise ValueError('Insufficient measured disk headroom')
    policy.enabled = True
    adopted = adopt_legacy(session)
    return dict(result, enabled=True, legacyReservations=adopted, pendingBytes=pending_bytes(session))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('execution', 'objects', 'database'):
        parser.add_argument('--' + name, required=True, help='Actual local persistent directory, never a URL')
    parser.add_argument('--enable', action='store_true', help='Explicit drained activation; no production defaults')
    parser.add_argument('--watch', action='store_true', help='Sample every 10 seconds; exit on measurement failure')
    for name in ('floor', 'api', 'cli'):
        parser.add_argument('--' + name + '-mib', type=int)
    args = parser.parse_args()
    settings = get_settings()
    if args.watch and (settings.db_pool_size != 1 or settings.db_max_overflow != 0
                       or settings.db_application_name != 'hx-capacity-observer'):
        parser.error('--watch requires DB_POOL_SIZE=1, DB_MAX_OVERFLOW=0, DB_APPLICATION_NAME=hx-capacity-observer')
    paths = {name: getattr(args, name) for name in ('execution', 'objects', 'database')}
    first = True
    while True:
        with session_factory().begin() as session:
            if args.enable and first:
                if any(getattr(args, name + '_mib') is None for name in ('floor', 'api', 'cli')):
                    parser.error('--enable requires all three measured budget arguments')
                result = enable(session, paths, args.floor_mib * MIB, args.api_mib * MIB, args.cli_mib * MIB)
            else:
                result = sample(session, paths)
        print(json.dumps(result), flush=True)
        first = False
        if not args.watch:
            break
        time.sleep(10)


if __name__ == '__main__':
    main()
