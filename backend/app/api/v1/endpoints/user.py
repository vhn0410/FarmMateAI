from fastapi import APIRouter, Depends
from app.infrastructure.db.models import UserModel
from app.core.security import get_current_user

router = APIRouter()

@router.get("/me")
def get_my_profile(current_user: UserModel = Depends(get_current_user)):
    """
    Frontend sẽ gọi API này ngay sau khi đăng nhập Keycloak thành công.
    Hàm get_current_user sẽ chạy ngầm và thực hiện đồng bộ (JIT) ngay lập tức!
    """
    return current_user