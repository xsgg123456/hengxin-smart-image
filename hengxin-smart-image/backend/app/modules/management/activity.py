"""Domestic management activity: existing usage facts plus read-only current queues."""
from collections import defaultdict
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts import activity as c
from app.db.session import get_session
from app.models import utcnow
from app.modules.auth.dependencies import CurrentUser
from app.modules.management.api_stats.projection import read_facts
from app.modules.management.api_usage import SHANGHAI, parse_day, utc
from app.modules.management.api_usage_summary import generation_type, summarize
from app.modules.management.activity_records import execution_records, group_status
from app.resource_models import UserRecord

router = APIRouter(tags=['management'])
CATEGORIES = {'api_request', 'cli_submission', 'cli_round', 'cli_candidate', 'version_published'}


def totals(facts):
    summary = summarize(facts)
    return c.Summary(images=summary.totalGeneratedImages, api=summary.apiAttempts, cli=summary.cliStarted)


def build_report(session, user, query):
    if user.role not in ('super_admin', 'design_manager'):
        raise HTTPException(403, '仅管理员和设计主管可查看调用与执行')
    start, end = parse_day(query.from_), parse_day(query.to)
    if start and end and start > end:
        raise HTTPException(422, '开始日期不能晚于结束日期')
    if query.userId and query.unassigned:
        raise HTTPException(422, '不能同时选择人员和未知操作者')
    try:
        actor = UUID(query.userId) if query.userId else None
    except ValueError as error:
        raise HTTPException(422, '统计人员 ID 无效') from error

    def matches(person, timestamp, kind):
        day = utc(timestamp).astimezone(SHANGHAI).date()
        return ((actor is None or person == actor) and (not query.unassigned or person is None)
            and (not start or day >= start) and (not end or day <= end)
            and (not query.generationType or kind == query.generationType))

    with session.no_autoflush:
        now = utcnow()
        users = session.scalars(select(UserRecord).order_by(UserRecord.name, UserRecord.id)).all()
        names = {u.id: u.name for u in users}
        facts = read_facts(session)
        entries = execution_records(session, facts, names, now)
    live = c.Live()
    for entry in entries:
        status = group_status(entry.row.status)
        if entry.row.current and status in ('queued', 'running', 'uncertain', 'failed'):
            setattr(live, status, getattr(live, status) + 1)
    filtered_facts = [fact for fact in facts if fact['category'] in CATEGORIES
        and matches(fact['operator_id'], fact['occurred_at'], generation_type(fact))]
    groups = defaultdict(list)
    for fact in filtered_facts:
        groups[fact['operator_id']].append(fact)
    people = [c.Person(id=str(person) if person else None, name=names.get(person, '未知操作者'),
        latest=max(utc(f['occurred_at']) for f in rows).isoformat(), **totals(rows).model_dump())
        for person, rows in groups.items()]
    people.sort(key=lambda person: (person.latest or '', person.id or ''), reverse=True)
    keyword = query.keyword.strip().casefold()
    selected = []
    for entry in entries:
        row = entry.row
        if not matches(UUID(row.personId) if row.personId else None,
                       entry.statistics_time or datetime.fromisoformat(row.createdAt), row.kind):
            continue
        if query.view == 'jobs':
            if query.currentOnly and not row.current:
                continue
            if query.status and group_status(row.status) != query.status:
                continue
            if keyword and keyword not in f'{row.task} {row.id}'.casefold():
                continue
        selected.append(entry)
    selected.sort(key=lambda entry: (entry.row.createdAt, entry.row.id), reverse=True)
    summary = totals(filtered_facts)
    if query.view == 'jobs' and (query.status or keyword or query.currentOnly):
        # Versions have no request foreign key. Do not guess an association by timestamp.
        summary = c.Summary(images=(sum(e.row.images for e in selected)
            if all(e.row.images is not None for e in selected) else None),
            api=sum(e.api for e in selected), cli=sum(e.cli for e in selected))
    offset = (query.page - 1) * query.pageSize
    return c.Report(checkedAt=now.isoformat(),
        users=[c.UserOption(id=str(u.id), name=u.name) for u in users], people=people,
        records=[e.row for e in selected[offset:offset + query.pageSize]], total=len(selected),
        page=query.page, pageSize=query.pageSize, summary=summary, live=live)


@router.get('/management/activity', response_model=c.Report)
def activity(query: Annotated[c.ActivityQuery, Query()], user: CurrentUser,
             session: Session = Depends(get_session)):
    return build_report(session, user, query)
