from fastapi import Depends, HTTPException

from app.modules.auth.dependencies import get_current_user

BUSINESS_ROLES = frozenset({'super_admin', 'design_manager', 'designer', 'operator'})
POLICIES = {
    'shared_resources': BUSINESS_ROLES,
    'manage_system': frozenset({'super_admin'}),
    'all_usage': frozenset({'super_admin', 'design_manager'}),
}


def authorize(user, permission='shared_resources'):
    if user is None:
        raise HTTPException(401, '请先登录')
    if user.status != 'active' or user.role not in POLICIES[permission]:
        raise HTTPException(403, '没有操作权限')
    return user


def require_permission(permission):
    def dependency(user=Depends(get_current_user)):
        return authorize(user, permission)
    return dependency
