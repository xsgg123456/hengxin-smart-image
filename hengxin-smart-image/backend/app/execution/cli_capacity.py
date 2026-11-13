"""All domestic Codex work shares the same execution limit."""
from sqlalchemy import func, select

from app.models import Job


KINDS = ('api_cli_edit', 'domestic_studio')
ACTIVE = ('running', 'collecting', 'cancelling', 'uncertain')


def active_count(session):
    return session.scalar(select(func.count()).select_from(Job).where(
        Job.kind.in_(KINDS), Job.status.in_(ACTIVE)))
