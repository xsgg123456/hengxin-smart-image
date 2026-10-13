from app.membership.routes import application_router
from app.overseas.members import membership
from app.overseas.permissions import require_permission

router = application_router('/api/overseas/v1/auth/identity', '/api/overseas/v1/members/applications',
                            membership, require_permission('members.manage'))
