import jwt
import requests
from jwt import PyJWKClient
from fastapi import HTTPException, status
from app.domain.interfaces.auth_provider import IAuthProvider
from app.core.config import settings


class KeycloakAuthProvider(IAuthProvider):
    def __init__(self):
        # Thiết lập Client để tải Public Key từ Keycloak về xác minh token
        self.jwks_client = PyJWKClient(
            f"{settings.keycloak_url}/protocol/openid-connect/certs"
        )

    def verify_token(self, token: str) -> dict:
        try:
            # Due to verify token when login in front end so 
            # using leeway to overcome it 
            # will refactor eventually
            clean_token = token.split(" ")[1] if token.startswith("Bearer ") else token
            signing_key = self.jwks_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                clean_token,
                signing_key.key,
                algorithms=["RS256"],
                options={"verify_aud": False},
                leeway=60
            )
            return {
                "user_id": payload.get("sub"),
                "username": payload.get("preferred_username"),
                "email": payload.get("email"),
                "full_name": payload.get("name"),
            }
        except Exception as e:
            # ĐÂY LÀ DÒNG QUAN TRỌNG NHẤT: In lỗi thật ra Terminal của Backend
            print(f"========== LỖI JWT NÈ: {repr(e)} ==========")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Lỗi thật sự là: {str(e)}",  # Đẩy thẳng lỗi lên giao diện cho dễ nhìn
            )

    def login(self, username: str, password: str) -> str:
        """
        Dịch lệnh cURL thành code Python.
        Gọi thẳng vào API Direct Access Grant của Keycloak để lấy Token.
        """
        token_url = f"{settings.keycloak_url}/protocol/openid-connect/token"

        # Payload y hệt như tham số -d trong lệnh curl của bạn
        payload = {
            "client_id": "iotlab",
            "grant_type": "password",
            "username": username,
            "password": password,
        }

        # Header y hệt như tham số -H trong lệnh curl
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        try:
            # Thực hiện lệnh POST sang server Keycloak
            response = requests.post(token_url, data=payload, headers=headers)

            # Nếu Keycloak từ chối (Sai pass, tài khoản khóa...)
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Sai tài khoản hoặc mật khẩu Keycloak",
                )

            # Lấy access_token từ JSON trả về
            token_data = response.json()
            return token_data.get("access_token")

        except requests.exceptions.RequestException as e:
            # Bắt lỗi nếu server Keycloak bị sập hoặc sai URL
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Không thể kết nối tới Keycloak: {str(e)}",
            )
