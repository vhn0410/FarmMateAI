from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from app.domain.interfaces.auth_provider import IAuthProvider
from app.core.dependencies import get_auth_provider

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
# Trỏ chính xác vào đường dẫn API đăng nhập Postgres của bạn
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
def get_current_user(
    token: str = Depends(oauth2_scheme),
    auth_provider: IAuthProvider = Depends(get_auth_provider)
) -> dict:
    """
    FastAPI tự động nạp Token, tự động nạp AuthProvider (Keycloak hoặc Postgres).
    Sau đó gọi hàm verify_token.
    """
    return auth_provider.verify_token(token)