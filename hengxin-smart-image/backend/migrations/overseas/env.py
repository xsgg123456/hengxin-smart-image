"""Overseas-only migration environment, with no domestic model imports."""
from alembic import context
from sqlalchemy import text

from app.core.config import get_settings
from app.overseas.auth import models  # noqa: F401 - register only overseas metadata
from app.overseas.members import models as member_models  # noqa: F401
from app.overseas.tasks import models as task_models  # noqa: F401
from app.overseas.materials import models as material_models  # noqa: F401
from app.overseas.execution import models as execution_models  # noqa: F401
from app.overseas.plans import models as plan_models  # noqa: F401
from app.overseas.pictures import models as picture_models
from app.overseas.archives import models as archive_models
from app.overseas.management import models as management_models
from app.overseas.db import (
    Base, VERSION_TABLE, get_engine, require_overseas_context,
    validate_migration_database,
)


require_overseas_context()

if context.is_offline_mode():
    context.configure(
        url=get_settings().database_url, target_metadata=Base.metadata,
        version_table=VERSION_TABLE, literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    # Validation queries autobegin; own the outer transaction so DDL commits too.
    with get_engine().begin() as connection:
        validate_migration_database(connection)
        context.configure(
            connection=connection, target_metadata=Base.metadata,
            version_table=VERSION_TABLE,
        )
        with context.begin_transaction():
            context.run_migrations()
        # Bootstrap grants DML on future business tables, but schema history is
        # owned exclusively by migrations. Standalone test DBs may omit this role.
        if connection.execute(text(
            "SELECT 1 FROM pg_roles WHERE rolname = 'overseas_app'"
        )).scalar():
            connection.execute(text(
                'REVOKE INSERT, UPDATE, DELETE ON overseas_alembic_version FROM overseas_app'
            ))
