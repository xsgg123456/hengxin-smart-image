from alembic import context

from app.db.session import get_engine
from app.models import Base
from app import resource_models  # noqa: F401 - register metadata for schema comparison
from app.modules.files import variants  # noqa: F401
from app.capacity import models as capacity_models  # noqa: F401
from app.modules.skills import models as skill_models  # noqa: F401
from app.modules.tasks import models as task_models  # noqa: F401
from app.modules.tasks import attempts as execution_models  # noqa: F401
from app.modules.templates import models as template_models  # noqa: F401
from app.modules.archives import models as archive_models  # noqa: F401
from app.modules.auth import models as auth_models  # noqa: F401
from app.modules.management import models as management_models  # noqa: F401
from app.worker import cleanup_models  # noqa: F401
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
    with get_engine().connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
