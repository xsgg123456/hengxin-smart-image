"""Independent overseas metadata; connection pooling stays in app.db.session."""
from sqlalchemy import inspect
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_business_context
from app.db.session import get_engine, get_session, session_factory  # noqa: F401


VERSION_TABLE = 'overseas_alembic_version'
SCHEMA_REVISION = 'overseas_0015'


class Base(DeclarativeBase):
    pass


def require_overseas_context():
    if get_business_context() != 'overseas':
        raise RuntimeError('Overseas migrations require HX_BUSINESS_CONTEXT=overseas')


def validate_migration_database(connection):
    """Fail before any DDL when configuration targets an unrelated database."""
    inspector = inspect(connection)
    if inspector.default_schema_name != 'public':
        raise RuntimeError('Overseas migrations require the public schema')
    for schema in inspector.get_schema_names():
        if schema == 'public' or schema == 'information_schema' or schema.startswith('pg_'):
            continue
        if (inspector.get_table_names(schema=schema)
                or inspector.get_view_names(schema=schema)
                or inspector.get_materialized_view_names(schema=schema)):
            raise RuntimeError('Unrecognized database schema; overseas migration refused')
    tables = set(inspector.get_table_names(schema='public'))
    if 'alembic_version' in tables:
        raise RuntimeError('Domestic migration marker found; overseas migration refused')
    allowed = {VERSION_TABLE, *Base.metadata.tables}
    if (tables - allowed or inspector.get_view_names(schema='public')
            or inspector.get_materialized_view_names(schema='public')):
        raise RuntimeError('Unrecognized database objects; overseas migration refused')
    if tables and VERSION_TABLE not in tables:
        raise RuntimeError('Missing overseas migration marker; migration refused')
