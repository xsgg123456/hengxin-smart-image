from alembic import context
from sqlalchemy import inspect

from app.core.config import get_business_context

if get_business_context() != 'domestic':
    raise RuntimeError('Domestic migrations require HX_BUSINESS_CONTEXT=domestic')

from app.db.session import get_engine
from app.models import Base
from app.execution import models as execution_models
from app.worker import models as worker_models
from app.modules.api_image_edits import deletion_models
from app import resource_models  # noqa: F401 - register metadata for schema comparison
from app.modules.files import variants  # noqa: F401
from app.capacity import models as capacity_models  # noqa: F401
from app.modules.auth import models as auth_models  # noqa: F401
from app.modules.auth import application_models  # noqa: F401
from app.modules.management import models as management_models  # noqa: F401
from app.modules.api_image_edits import models as api_image_models  # noqa: F401
from app.modules.api_image_edits import conversation_models  # noqa: F401
from app.retention import models as retention_models  # noqa: F401
from app.modules.management.api_stats import models as api_usage_models  # noqa: F401
from app.modules.api_image_edits import heartbeat_models  # noqa: F401

if context.is_offline_mode():
    from app.core.config import get_settings
    context.configure(url=get_settings().database_url, target_metadata=Base.metadata,
                      literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    with get_engine().begin() as connection:
        if inspect(connection).has_table('overseas_alembic_version', schema='public'):
            raise RuntimeError('Overseas migration marker found; domestic migration refused')
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
