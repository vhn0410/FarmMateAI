from fastapi import APIRouter, Depends
from app.infrastructure.db.models import UserModel
from app.core.security import get_current_user

router = APIRouter()


@router.get("/me")
def get_my_profile(current_user: UserModel = Depends(get_current_user)):
    """
    The frontend calls this API immediately after a successful Keycloak login.
    The get_current_user function resolves the user lazily and synchronously on demand.
    """
    return current_user