from fastapi import APIRouter

from app.contracts.business import User
from app.modules.auth.dependencies import CurrentUser

router = APIRouter(tags=['auth'])


@router.get('/auth/me', response_model=User)
def me(user: CurrentUser):
    return User(id=str(user.id), name=user.name, role=user.role, status=user.status)
