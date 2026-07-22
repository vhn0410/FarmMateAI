from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from app.domain.interfaces.auth_provider import IAuthProvider
from app.core.dependencies import get_auth_provider
from app.infrastructure.db.models import UserModel
from app.core.config import settings
from sqlalchemy.orm import Session
from app.infrastructure.db.session import get_db

# Point to the correct login endpoint for Postgres auth
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    auth_provider: IAuthProvider = Depends(get_auth_provider),
    db: Session = Depends(get_db),  # Inject the database session here
):
    # 1. Ask the provider (Keycloak/Postgres) to verify the token
    token_data = auth_provider.verify_token(token)
    user_id = token_data.get("user_id")

    # 2. Look up the user in the local database
    user = db.query(UserModel).filter(UserModel.id == user_id).first()

    # 3. JIT provisioning (shadow user)
    if not user:
        print("DB execute.......................................")
        # If using Keycloak and the user is not yet in the DB, create them automatically
        if settings.auth_mode == "keycloak":
            user = UserModel(
                id=user_id,
                username=token_data.get("username"),
                email=token_data.get("email"),
                full_name=token_data.get("full_name"),
                auth_provider="keycloak",
                role="user",
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            # If using pure Postgres auth and the user is missing, the token is invalid
            raise HTTPException(status_code=401, detail="User does not exist in the system")

    # 4. Return the fully populated user object for other APIs (such as chat)
    return user


def get_admin_user(current_user: UserModel = Depends(get_current_user)):
    """
    Dependency to verify whether the current user has admin rights.
    Use this after get_current_user to ensure the user is logged in.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to access this feature. Admin role required.",
        )
    return current_user
