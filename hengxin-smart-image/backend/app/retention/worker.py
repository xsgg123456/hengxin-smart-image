"""Run on the owning native CLI worker: --once, or hourly with --loop."""
import argparse
import json
import time
from pathlib import Path
from sqlalchemy import exists, select
from app.core.config import get_settings
from app.db.session import session_factory
from app.models import utcnow
from app.modules.tasks.models import TaskRecord
from app.modules.api_image_edits.conversation_models import Conversation
from app.modules.api_image_edits.models import ApiItem, ApiTask
from app.storage.minio_store import get_store
from .models import RetentionEntry
from .state import touch
from .objects import retry_objects


def register_existing(factory, limit, now):
    """First discovery starts the grace period; no historical timestamp backdating."""
    for domain, model in [('legacy_cli', TaskRecord), ('api_cli', Conversation)]:
        with factory() as session:
            query = select(model.id).where(~exists().where(
                RetentionEntry.domain == domain, RetentionEntry.resource_id == model.id,
                RetentionEntry.initialized_at.is_not(None)))
            if domain == 'legacy_cli':
                query = query.where(TaskRecord.execution_source == 'cli')
            ids = session.scalars(query.order_by(model.id).limit(limit)).all()
        for identifier in ids:
            with factory.begin() as session:
                if domain == 'api_cli':
                    conversation = session.get(Conversation, identifier)
                    if conversation is None:
                        continue
                    item = session.get(ApiItem, conversation.item_id)
                    parent = session.scalar(select(ApiTask).where(ApiTask.id == item.task_id)
                                            .with_for_update(skip_locked=True))
                else:
                    parent = session.scalar(select(TaskRecord).where(TaskRecord.id == identifier)
                                            .with_for_update(skip_locked=True))
                if parent is None:
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
    from . import api, legacy
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
        adapter = {'api_cli': api, 'legacy_cli': legacy}.get(domain)
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
    args = parser.parse_args()
    while True:
        print(json.dumps(run_once(), ensure_ascii=False), flush=True)
        if args.once:
            return
        time.sleep(3600)


if __name__ == '__main__':
    main()
