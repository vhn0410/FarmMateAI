from fastapi import Depends
from sqlalchemy.orm import Session

from app.domain.interfaces.auth_provider import IAuthProvider
from app.infrastructure.auth.keycloak_auth import KeycloakAuthProvider
from app.infrastructure.auth.postgres_auth import PostgresAuthProvider
from app.infrastructure.repositories.user_repository import SqlAlchemyUserRepository
from app.core.config import settings

# Giả sử bạn đã có hàm get_db() trả về session trong file này
from app.infrastructure.db.session import get_db 

def get_auth_provider(db: Session = Depends(get_db)) -> IAuthProvider:
    """
    Công tắc chuyển đổi Auth. 
    Tự động tiêm Database Session nhờ FastAPI Depends.
    """
    if settings.auth_mode == "keycloak":
        return KeycloakAuthProvider()
        
    elif settings.auth_mode == "postgres":
        # 1. Khởi tạo Repository với DB Session
        user_repo = SqlAlchemyUserRepository(db)
        # 2. Tiêm Repository vào Auth Provider
        return PostgresAuthProvider(user_repo=user_repo) 
        
    else:
        raise ValueError(f"Chưa cấu hình hoặc cấu hình sai AUTH_MODE: {settings.auth_mode}")