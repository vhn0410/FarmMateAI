import jwt
from jwt import PyJWKClient
from fastapi import HTTPException, status
from app.domain.interfaces.auth_provider import IAuthProvider
from app.core.config import settings

class KeycloakAuthProvider(IAuthProvider):
    def __init__(self):
        self.jwks_client = PyJWKClient(f"{settings.keycloak_url}/protocol/openid-connect/certs")

    def verify_token(self, token: str) -> dict:
        try:
            signing_key = self.jwks_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token, signing_key.key, algorithms=["RS256"], options={"verify_aud": False}
            )
            return {"user_id": payload.get("sub"), "username": payload.get("preferred_username")}
        except jwt.PyJWTError:
            raise HTTPException(status_code=401, detail="Keycloak Token không hợp lệ")

    def login(self, username: str, password: str) -> str:
        # Với Keycloak, FE thường gọi thẳng Keycloak để lấy token. 
        # Nếu BE muốn gọi, bạn dùng thư viện requests gửi HTTP POST tới Keycloak ở đây.
        raise NotImplementedError("Sử dụng Direct Access Grant API của Keycloak")