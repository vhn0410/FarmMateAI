from abc import ABC, abstractmethod
from typing import Dict, Any


class IAuthProvider(ABC):
    @abstractmethod
    def verify_token(self, token: str) -> Dict[str, Any]:
        """
        Kiểm tra tính hợp lệ của Token và trả về thông tin User.
        Nếu lỗi, ném ra HTTPException(401).
        """
        pass

    @abstractmethod
    def login(self, username: str, password: str) -> str:
        """
        Xử lý đăng nhập và trả về chuỗi JWT Token.
        (Chủ yếu dùng cho Postgres, Keycloak thường gọi thẳng lên server của họ).
        """
        pass
