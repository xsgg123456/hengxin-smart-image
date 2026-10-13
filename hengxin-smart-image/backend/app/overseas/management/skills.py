"""Browser Skill management is a read-only view of verified installations."""
from .installed_catalog import listing


def list_skills(session):
    return {'items': listing()}
