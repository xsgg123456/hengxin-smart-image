"""Transaction-local writers; callers own commit and the existing business locks."""
from sqlalchemy import select
from app.models import utcnow
from .models import ApiUsageFact

FIELDS = ('key', 'category', 'channel', 'kind', 'task_id', 'task_name', 'owner_id',
          'operator_id', 'occurred_at', 'completed_at', 'state', 'quantity', 'is_retry', 'attribution')


def as_dict(row):
    data = {field: getattr(row, field) for field in FIELDS}
    if data['category'] == 'cli_submission':
        data['state'] = 'submitted'  # An accepted submission is an immutable action, not a round snapshot.
    return data


def fact(task, category, source_id, *, channel='api', kind='legacy_unknown',
         operator_id=None, occurred_at=None, completed_at=None, state='succeeded',
         quantity=1, is_retry=None, attribution='historical_unverified'):
    return dict(key=f'{category}:{source_id}', category=category, channel=channel, kind=kind,
                task_id=task.id, task_name=task.name, owner_id=task.owner_id,
                operator_id=operator_id, occurred_at=occurred_at or utcnow(),
                completed_at=completed_at, state=state, quantity=quantity,
                is_retry=is_retry, attribution=attribution)


def put(session, data, *, update=False, replace=False):
    # Native conflict handling also makes concurrent explicit backfills idempotent.
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    dialect = session.get_bind().dialect.name
    insert = pg_insert if dialect == 'postgresql' else sqlite_insert
    statement = insert(ApiUsageFact).values(**data)
    if replace:
        statement = statement.on_conflict_do_update(index_elements=['key'], set_={
            **{key: value for key, value in data.items() if key != 'key'}, 'updated_at': utcnow()})
    elif update:
        statement = statement.on_conflict_do_update(index_elements=['key'], set_={
            'state': data['state'], 'completed_at': data['completed_at'], 'updated_at': utcnow()})
    else:
        statement = statement.on_conflict_do_nothing(index_elements=['key'])
    return int(session.execute(statement.returning(ApiUsageFact.key)).scalar_one_or_none() is not None)


def record_task(session, task):
    put(session, fact(task, 'task_created', task.id, kind='task_created',
                      operator_id=task.operator_id, occurred_at=task.created_at, attribution='verified'))


def record_attempt(session, item, task, attempt, *, started=False):
    # A human confirming process termination is not evidence of an upstream return.
    state = 'uncertain' if attempt.resolved_by else attempt.state
    existing = session.scalar(select(ApiUsageFact).where(ApiUsageFact.key == f'api_request:{attempt.id}'))
    if existing:
        data = as_dict(existing)
        data.update(state=state, completed_at=attempt.completed_at)
    else:
        data = fact(task, 'api_request', attempt.id, operator_id=attempt.operator_id,
                    kind=(item.revision_snapshot or {}).get('kind', 'generation') if started else 'legacy_unknown',
                    occurred_at=attempt.created_at, completed_at=attempt.completed_at,
                    state=state, is_retry=(bool(item.cycle_retries or item.request_is_retry)
                                                  if started else None),
                    attribution='verified' if started and item.request_operator_id else 'historical_unverified')
    put(session, data, update=True)


def record_version(session, item, task, version):
    put(session, fact(task, 'version_published', version.id, kind=version.kind or 'legacy_unknown',
                      operator_id=version.operator_id, occurred_at=version.created_at,
                      attribution='verified' if item.request_operator_id else 'historical_unverified'))


def record_turn(session, task, turn, *, spawned=False):
    if spawned:
        existing = session.scalar(select(ApiUsageFact).where(ApiUsageFact.key == f'cli_round:{turn.id}'))
        if existing is None or existing.quantity == 0 or existing.attribution != 'verified':
            put(session, fact(task, 'cli_round', turn.id, channel='cli', kind='image_edit',
                             operator_id=turn.operator_id, occurred_at=utcnow(), state=turn.status,
                             is_retry=False, attribution='verified'), replace=True)
    existing = session.scalar(select(ApiUsageFact).where(ApiUsageFact.key == f'cli_round:{turn.id}')
                              .execution_options(populate_existing=True))
    if existing:
        data = as_dict(existing)
        data.update(state=turn.status, completed_at=turn.finished_at)
        put(session, data, update=True)
    if turn.candidate_id:
        put(session, fact(task, 'cli_candidate', turn.id, channel='cli', kind='image_edit',
                         operator_id=turn.operator_id, occurred_at=turn.finished_at,
                         attribution='verified'))


def record_action(session, task, category, identifier, operator_id, *, channel='api'):
    put(session, fact(task, category, identifier, channel=channel, kind=category,
                      operator_id=operator_id, attribution='verified',
                      state='submitted' if category == 'cli_submission' else 'succeeded'))
