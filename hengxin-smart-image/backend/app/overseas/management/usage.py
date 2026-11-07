from datetime import timezone
from sqlalchemy import func, select
from app.overseas.execution.models import Job
from app.overseas.pictures.models import PictureVersion
from .facts import scoped


def read(session, actor, clauses):
    # Do not fetch frozen materials/prompts merely to aggregate management facts.
    jobs = session.execute(scoped(session, actor, clauses).with_only_columns(
        Job.status)).all()
    result = {key: 0 for key in ('jobs', 'queued', 'running', 'uncertain', 'succeeded', 'failed',
                                  'cancelled', 'generationImages', 'revisionImages')}
    result['jobs'] = len(jobs)
    for job in jobs:
        result['running' if job.status in ('running', 'collecting', 'cancelling') else job.status] += 1
    ids = scoped(session, actor, clauses).with_only_columns(Job.id)
    counts = session.execute(select(Job.kind, func.count()).select_from(PictureVersion)
        .join(Job, Job.id == PictureVersion.job_id).where(Job.id.in_(ids)).group_by(Job.kind))
    for kind, count in counts:
        if kind in ('generation', 'revision'):
            result[kind + 'Images'] = count
    from app.overseas.studio.models import Picture, Turn
    studio_images = session.scalar(select(func.count()).select_from(Picture).join(
        Turn, Turn.id == Picture.turn_id).where(Turn.job_id.in_(ids)))
    result['generationImages'] += studio_images
    return result


def people(session, actor, clauses):
    """Count persisted studio requests, not executor claims or unknown legacy jobs."""
    from app.overseas.auth.models import Member
    from app.overseas.studio.models import Picture, Turn
    requests = scoped(session, actor, clauses).where(Turn.id.is_not(None)).with_only_columns(
        Job.id.label('job_id'), Job.created_at.label('created_at'), Turn.id.label('turn_id'),
        Turn.actor_id.label('actor_id')).subquery()
    rows = session.execute(select(requests.c.actor_id, Member.name, func.count().label('calls'),
        func.max(requests.c.created_at)).outerjoin(Member, Member.id == requests.c.actor_id)
        .group_by(requests.c.actor_id, Member.name).order_by(Member.name, requests.c.actor_id)).all()
    counts = dict(session.execute(select(requests.c.actor_id, func.count(Picture.id))
        .join(Picture, Picture.turn_id == requests.c.turn_id).group_by(requests.c.actor_id)).all())
    for member_id, count in session.execute(select(requests.c.actor_id, func.count(PictureVersion.id))
            .join(PictureVersion, PictureVersion.job_id == requests.c.job_id).group_by(requests.c.actor_id)):
        counts[member_id] = counts.get(member_id, 0) + count
    return {'items': [{'id': str(member_id), 'name': name or '历史用户', 'calls': calls,
                       'images': counts.get(member_id, 0), 'lastCall': latest.replace(tzinfo=timezone.utc)
                       if latest and latest.tzinfo is None else latest}
                      for member_id, name, calls, latest in rows]}
