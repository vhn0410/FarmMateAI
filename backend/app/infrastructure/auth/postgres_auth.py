import jwt
import datetime
from fastapi import HTTPException, status
from passlib.context import CryptContext

from app.domain.interfaces.auth_provider import IAuthProvider
from app.domain.interfaces.repositories.user_repository import IUserRepository
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class PostgresAuthProvider(IAuthProvider):
    def __init__(self, user_repo: IUserRepository):
        # Tiêm Repository interface vào thay vì tiêm db_session trực tiếp
        self.user_repo = user_repo
        self.secret_key = settings.jwt_secret_key
        self.algorithm = "HS256"

    def verify_token(self, token: str) -> dict:
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return {
                "user_id": payload.get("user_id"),
                "username": payload.get("username"),
                "email": None,            # waiting for implementing register account function
                "full_name": None         # waiting for implementing register account function
            }
        except jwt.PyJWTError:
            raise HTTPException(
                status_code=401, detail="Token không hợp lệ hoặc đã hết hạn"
            )

    def login(self, username: str, password: str) -> str:
        # 1. Gọi Repo để lấy Domain Entity, hoàn toàn sạch sẽ không dính dáng ORM code ở đây
        user = self.user_repo.get_by_username(username)

        # 2. Kiểm tra mật khẩu dựa trên Entity nhận được
        if not user or not pwd_context.verify(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Tài khoản hoặc mật khẩu không chính xác",
            )

        # 3. Phát hành Token
        expire = datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        payload = {"user_id": user.id, "username": user.username, "exp": expire}
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
