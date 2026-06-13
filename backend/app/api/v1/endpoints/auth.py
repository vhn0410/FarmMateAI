from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from app.core.dependencies import get_auth_provider
from app.domain.interfaces.auth_provider import IAuthProvider

router = APIRouter()

@router.post("/login")
def login_for_access_token(
    # OAuth2PasswordRequestForm tự động lấy username/password từ ô nhập của Swagger UI
    form_data: OAuth2PasswordRequestForm = Depends(),
    auth_provider: IAuthProvider = Depends(get_auth_provider)
):
    """
    API xử lý đăng nhập.
    Tự động gọi vào Provider hiện tại (Postgres hoặc Keycloak) để cấp Token.
    """
    token = auth_provider.login(
        username=form_data.username, 
        password=form_data.password
    )
    
    # Bắt buộc trả về format JSON này để Swagger UI hiểu và đóng ổ khóa
    return {
        "access_token": token, 
        "token_type": "bearer"
    }