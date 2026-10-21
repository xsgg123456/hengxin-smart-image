from datetime import datetime, time, timedelta, timezone
from sqlalchemy import func, select
from app.core.config import get_settings
from .observability_models import RetentionRecord, RetentionRun, RetentionService, RetentionTotals
from .queries import BEIJING, pending_query
from .state import aware


def summary(session, now):
    settings = get_settings()
    beat = session.get(RetentionService, 'api_cli')
    run = session.scalar(select(RetentionRun).order_by(RetentionRun.started_at.desc(), RetentionRun.id.desc()).limit(1))
    totals = session.get(RetentionTotals, 'api_cli')
    state = 'disabled' if not settings.cli_retention_enabled else 'unknown'
    if settings.cli_retention_enabled and beat:
        state = 'online' if timedelta(0) <= now - aware(beat.heartbeat_at) <= timedelta(seconds=120) else 'offline'
    pending = pending_query(session, now).subquery()
    count = lambda *conditions: session.scalar(select(func.count()).select_from(pending).where(*conditions))
    today = datetime.combine(now.astimezone(BEIJING).date(), time.min, BEIJING).astimezone(timezone.utc)
    def successful(kind):
        return session.scalar(select(func.count()).select_from(RetentionRecord).where(
            RetentionRecord.kind == kind, RetentionRecord.counted.is_(True),
            RetentionRecord.completed_at >= today, RetentionRecord.completed_at < today + timedelta(days=1)))
    stamp = lambda value: aware(value).isoformat() if value else None
    return dict(checkedAt=stamp(now), policy=dict(enabled=settings.cli_retention_enabled,
        cacheIdleHours=24, historyIdleHours=72, batchSize=min(settings.cli_retention_batch_size, 25),
        scanIntervalSeconds=3600, detailRetentionDays=90),
        service=dict(state=state, heartbeatAt=stamp(beat.heartbeat_at) if beat else None,
            scanState=run.status if run else 'unknown', lastStartedAt=stamp(run.started_at) if run else None,
            lastFinishedAt=stamp(run.finished_at) if run else None,
            nextScanAt=stamp(beat.next_scan_at) if beat else None),
        statisticsSince=stamp(totals.since) if totals else None,
        counts=dict(cacheToday=successful('cache'), historyToday=successful('history'),
            cacheTotal=totals.cache_total if totals else 0, historyTotal=totals.history_total if totals else 0,
            retry=count(pending.c.result == 'retry'), overdue=count(pending.c.due_at <= now),
            protected=count(pending.c.result == 'protected'), objectsPending=count(pending.c.objects_pending > 0)))
