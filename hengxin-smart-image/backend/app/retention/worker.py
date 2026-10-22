"""Run on the owning native CLI worker: --once, or hourly with --loop."""
import argparse
import json
import time
from pathlib import Path
from sqlalchemy import exists, select
from app.core.config import get_settings
from app.db.session import session_factory
from app.models import utcnow
from app.modules.api_image_edits.conversation_models import Conversation, ConversationTurn
from app.modules.api_image_edits.models import ApiItem, ApiTask
from app.storage.minio_store import get_store
from .models import RetentionEntry
from .state import touch, aware, CACHE_AGE, HISTORY_AGE
from .objects import retry_objects
from app.execution.cleanup_diagnostics import report


def register_existing(factory, limit, now):
    """Preserve tracked activity; recover missing baselines from durable activity."""
    domain = 'api_cli'
    with factory() as session:
        ids = session.scalars(select(Conversation.id).where(~exists().where(
            RetentionEntry.domain == domain, RetentionEntry.resource_id == Conversation.id,
            RetentionEntry.initialized_at.is_not(None))).order_by(Conversation.id).limit(limit)).all()
    for identifier in ids:
        with factory.begin() as session:
            conversation = session.get(Conversation, identifier)
            item = session.get(ApiItem, conversation.item_id) if conversation else None
            if item is None:
                continue
            parent = session.scalar(select(ApiTask).where(ApiTask.id == item.task_id)
                                    .with_for_update(skip_locked=True))
            if parent is None:
                continue
            from app.modules.api_image_edits.deletion_state import fenced
            if fenced(session, parent.id):
                continue
            row = session.scalar(select(RetentionEntry).where(
                RetentionEntry.domain == domain, RetentionEntry.resource_id == identifier))
            if row is None or row.initialized_at is None:
                if row is None:
                    dates = [conversation.updated_at, conversation.created_at]
                    for turn in session.scalars(select(ConversationTurn).where(
                            ConversationTurn.conversation_id == identifier)):
                        dates.extend([turn.created_at, turn.finished_at])
                        if turn.adopted_version is not None:
                            dates.append(turn.updated_at)
                    baseline = max(aware(value) for value in dates if value is not None)
                    row = touch(session, domain, identifier, baseline)
                elif row.status == 'active':
                    row.next_cleanup_at = aware(row.last_activity_at) + (
                        CACHE_AGE if row.cache_cleared_at is None else HISTORY_AGE)
                row.initialized_at = now


def run_once(factory=None, store=None, settings=None, now=None):
    settings, now = settings or get_settings(), now or utcnow()
    if not settings.cli_retention_enabled:
        return {'status': 'disabled'}
    factory = factory or session_factory()
    # SQLite tests verify individual operations; the real scheduler requires row locks.
    with factory() as session:
        if session.get_bind().dialect.name != 'postgresql':
            return {'status': 'unsupported_database'}
    from .service import begin_scan, end_scan
    scan_id = begin_scan(factory, now)
    try:
        result = scan(factory, store or get_store(), settings, now)
    except Exception as error:
        report(error, stage='scan', resource_id=scan_id)
        end_scan(factory, scan_id, 'failed')
        raise
    end_scan(factory, scan_id, result['status'])
    return result


def scan(factory, store, settings, now):
    from . import api
    limit = min(settings.cli_retention_batch_size, 25)
    register_existing(factory, limit, now)
    with factory() as session:
        entries = session.execute(select(RetentionEntry.domain, RetentionEntry.resource_id).where(
            RetentionEntry.next_cleanup_at <= now, RetentionEntry.status != 'expired')
            .where(RetentionEntry.initialized_at.is_not(None))
            .order_by(RetentionEntry.next_cleanup_at, RetentionEntry.id).limit(limit)).all()
    results, failed = [], False
    for domain, identifier in entries:
        adapter = {'api_cli': api}.get(domain)
        if adapter is None:
            continue
        try:
            status = adapter.process(factory, store, Path(settings.codex_execution_root), identifier, now)
        except Exception as error:
            report(error, stage='resource_scan', resource_id=identifier)
            status = 'retry'  # A concurrent lock conflict does not terminate the batch.
            failed = True  # Persist this scan failure even when no resource lock was obtained.
        results.append({'domain': domain, 'resourceId': str(identifier), 'status': status})
    return {'status': 'failed' if failed else 'completed', 'resources': results,
            'objectsRemoved': retry_objects(factory, store, limit, now)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--once', action='store_true')
    mode.add_argument('--loop', action='store_true')
    parser.add_argument('--deletions-only', action='store_true',
                        help='Run explicit API task deletions independently of automatic retention')
    parser.add_argument('--interval', type=int, default=5)
    args = parser.parse_args()
    if args.interval < 1:
        parser.error('--interval must be positive')
    try:
        if not args.deletions_only and get_settings().cli_retention_enabled:
            from .service import beating
            with beating(session_factory()):
                execute_loop(args)
        else:
            execute_loop(args)
    except Exception as error:
        report(error, stage='worker_lifecycle', resource_id=None)
        raise SystemExit(1) from None


def execute_loop(args):
    while True:
        try:
            if args.deletions_only:
                from app.modules.api_image_edits.deletion import run_pending
                result = run_pending(session_factory(), get_store())
            else:
                result = run_once()
            print(json.dumps(result, ensure_ascii=False), flush=True)
        except Exception as error:
            report(error, stage='worker_loop', resource_id=None)
            if args.once:
                raise SystemExit(1) from None
            print(json.dumps({'status': 'unavailable'}), flush=True)
        if args.once:
            return
        time.sleep(args.interval if args.deletions_only else 3600)


if __name__ == '__main__':
    main()
