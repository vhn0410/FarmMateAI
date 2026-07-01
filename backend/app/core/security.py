from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from app.domain.interfaces.auth_provider import IAuthProvider
from app.core.dependencies import get_auth_provider
from app.infrastructure.db.models import UserModel
from app.core.config import settings
from sqlalchemy.orm import Session
from app.infrastructure.db.session import get_db

# Trỏ chính xác vào đường dẫn API đăng nhập Postgres của bạn
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    auth_provider: IAuthProvider = Depends(get_auth_provider),
    db: Session = Depends(get_db),  # Bơm Database Session vào đây
):
    # 1. Nhờ Provider (Keycloak/Postgres) giải mã Token
    token_data = auth_provider.verify_token(token)
    user_id = token_data.get("user_id")

    # 2. Tìm user trong CSDL nội bộ
    user = db.query(UserModel).filter(UserModel.id == user_id).first()

    # 3. KỸ THUẬT JIT PROVISIONING (SHADOW USER)
    if not user:
        print("DB execute.......................................")
        # Nếu đang xài Keycloak mà user chưa có trong DB -> Tự động tạo!
        if settings.auth_mode == "keycloak":
            user = UserModel(
                id=user_id,  # Lấy chính xác chuỗi 'sub' làm Khóa chính
                username=token_data.get("username"),
                email=token_data.get("email"),
                full_name=token_data.get("full_name"),
                auth_provider="keycloak",
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            # Nếu đang xài Postgres thuần mà ko thấy user -> Token giả mạo
            raise HTTPException(
                status_code=401, detail="User không tồn tại trong hệ thống"
            )

    # 4. Trả về object User hoàn chỉnh cho các API khác xài (như API chat)
    return user
