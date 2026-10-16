"""Run on the owning native CLI worker: --once, or hourly with --loop."""
import argparse
import json
import time
from pathlib import Path
from sqlalchemy import exists, select
from app.core.config import get_settings
from app.db.session import session_factory
from app.models import utcnow
from app.modules.api_image_edits.conversation_models import Conversation
from app.modules.api_image_edits.models import ApiItem, ApiTask
from app.storage.minio_store import get_store
from .models import RetentionEntry
from .state import touch
from .objects import retry_objects


def register_existing(factory, limit, now):
    """First discovery starts the grace period; no historical timestamp backdating."""
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
                if row is None or row.status == 'active':
                    row = touch(session, domain, identifier, now)
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
    from . import api
    store = store or get_store()
    limit = settings.cli_retention_batch_size
    register_existing(factory, limit, now)
    with factory() as session:
        entries = session.execute(select(RetentionEntry.domain, RetentionEntry.resource_id).where(
            RetentionEntry.next_cleanup_at <= now, RetentionEntry.status != 'expired')
            .where(RetentionEntry.initialized_at.is_not(None))
            .order_by(RetentionEntry.next_cleanup_at, RetentionEntry.id).limit(limit)).all()
    results = []
    for domain, identifier in entries:
        adapter = {'api_cli': api}.get(domain)
        if adapter is None:
            continue
        try:
            status = adapter.process(factory, store, Path(settings.codex_execution_root), identifier, now)
        except Exception:
            status = 'retry'  # A concurrent lock conflict does not terminate the batch.
        results.append({'domain': domain, 'resourceId': str(identifier), 'status': status})
    return {'status': 'completed', 'resources': results, 'objectsRemoved': retry_objects(factory, store, limit, now)}


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
    while True:
        try:
            if args.deletions_only:
                from app.modules.api_image_edits.deletion import run_pending
                result = run_pending(session_factory(), get_store())
            else:
                result = run_once()
            print(json.dumps(result, ensure_ascii=False), flush=True)
        except Exception:
            if args.once:
                raise
            print(json.dumps({'status': 'unavailable'}), flush=True)
        if args.once:
            return
        time.sleep(args.interval if args.deletions_only else 3600)


if __name__ == '__main__':
    main()
