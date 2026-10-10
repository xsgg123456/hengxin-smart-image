"""Explicit idempotent backfill: python -m app.modules.management.api_stats.backfill."""
from sqlalchemy import select
from .facts import put
from .models import ApiUsageFact
from .projection import historical_facts


def preserve(session, task_id=None):
    stored = session.scalars(select(ApiUsageFact)).all()
    rows = historical_facts(session, task_id=task_id, adopted_keys={r.key for r in stored},
        verified_submissions={r.key for r in stored if r.attribution == 'verified'})
    return sum(put(session, row) for row in sorted(rows, key=lambda row: row['key']))


def main():
    from app.db.session import session_factory
    with session_factory().begin() as session:
        count = preserve(session)
    print(f'新增统计事实：{count}')


if __name__ == '__main__':
    main()
