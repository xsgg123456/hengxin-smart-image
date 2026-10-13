from app.membership.routes import application_router
from app.modules.auth import membership
from app.modules.auth.permissions import require_permission

router = application_router('/api/v1/auth/identity', '/api/v1/management/users/applications',
                            membership, require_permission('manage_system'))
