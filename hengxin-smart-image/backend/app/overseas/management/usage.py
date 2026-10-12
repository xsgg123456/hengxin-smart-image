from sqlalchemy import func, select
from app.overseas.execution.models import Job
from app.overseas.pictures.models import PictureVersion
from .facts import scoped, token


def read(session, actor, clauses):
    # Do not fetch frozen materials/prompts merely to aggregate management facts.
    jobs = session.execute(scoped(session, actor, clauses).with_only_columns(
        Job.status, Job.execution_count, Job.usage)).all()
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
    executed = [job for job in jobs if job.execution_count > 0]
    for name, field in (('inputTokens', 'input_tokens'), ('outputTokens', 'output_tokens')):
        counters = [token(job, field) for job in executed]
        result[name] = sum(counters) if counters and all(v is not None for v in counters) else None
    result['cost'] = None
    return result
