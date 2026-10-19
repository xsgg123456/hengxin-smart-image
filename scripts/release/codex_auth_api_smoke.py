"""Installed-image public error projection checks; no network or production DB."""
from types import SimpleNamespace as NS
from uuid import uuid4

from app.overseas.execution import events
from app.overseas.management import monitor


class Query:
    def __getattr__(self, _):
        return lambda *args, **kwargs: self


def check(error, expected):
    job = NS(id=uuid4(), task_id=uuid4(), kind='studio', status='failed', version=1,
             error=error, created_at=None, started_at=None, completed_at=None, execution_count=1)
    assert events.serialize(job)['error'] == expected
    row = NS(id=1, job_id=job.id, status='failed', message=error, created_at=None)
    session = NS(scalars=lambda _: NS(all=lambda: [row]))
    assert events.read(session, job.task_id)['items'][0]['message'] == expected
    monitor.scoped = lambda *_: Query()
    monitor.image_counts = lambda *_: {}
    # SQL construction needs an actual selectable for count(), but never executes SQL.
    from sqlalchemy import select
    from app.overseas.execution.models import Job
    query = Query()
    query.subquery = lambda: select(Job).subquery()
    monitor.scoped = lambda *_: query
    session = NS(scalar=lambda _: 1, execute=lambda _: NS(all=lambda: [(job, 'task', None, None)]))
    assert monitor.read(session, None, [], 1, 20)['items'][0]['error'] == expected


for code in ('authentication_failed', 'credentials_invalid', 'credentials_account_changed',
             'credentials_busy', 'credentials_refresh_failed', 'timeout', 'output_limit', 'execution_failed'):
    check(code, events.FAILURES[code])
    check(events.FAILURES[code], events.FAILURES[code])
check('untrusted raw stderr token=secret /private/path', events.MESSAGES['failed'])
print('API_INSTALLED_PUBLIC_ERROR_PROJECTIONS_PASS')
