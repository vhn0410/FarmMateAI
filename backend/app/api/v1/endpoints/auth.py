from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
import requests

from pydantic import BaseModel
from typing import Optional

from app.core.dependencies import get_auth_provider, get_user_repository
from app.domain.interfaces.auth_provider import IAuthProvider
from app.domain.interfaces.repositories.user_repository import IUserRepository
from app.core.security import get_current_user, oauth2_scheme
from app.infrastructure.api.aaem_client import AAEMClient
from app.infrastructure.api.ppm_client import PPMClient
from app.infrastructure.auth.postgres_auth import pwd_context

router = APIRouter()

class UserRegisterRequest(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: str = "user"

@router.post("/register")
def register_user(
    request: UserRegisterRequest,
    user_repo: IUserRepository = Depends(get_user_repository)
):
    """
    API đăng ký user mới.
    """
    # Check existing
    existing = user_repo.get_by_username(request.username)
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    hashed_password = pwd_context.hash(request.password)
    
    user_data = {
        "username": request.username,
        "hashed_password": hashed_password,
        "email": request.email,
        "full_name": request.full_name,
        "role": request.role,
        "auth_provider": "postgres"
    }
    
    user_repo.create_user(user_data)
    
    return {"status": "success", "message": "User registered successfully"}

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

@router.get("/verify")
def verify_token(
    current_user: dict = Depends(get_current_user),
    token: str = Depends(oauth2_scheme)
):
    """
    API dùng để Frontend Health Check.
    Kiểm tra token có hợp lệ không (bao gồm cả việc check với upstream AAEM API).
    """
    try:
        aaem_client = AAEMClient()
        aaem_client.get_agri_areas(token)
        
        ppm_client = PPMClient()
        ppm_client.get_projects(token)
        
        return {"status": "ok", "message": "Token is valid", "user": current_user}
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 401:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired in upstream service"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error verifying token with upstream"
        )