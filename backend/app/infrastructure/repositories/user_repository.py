from typing import Optional
from sqlalchemy.orm import Session
from app.domain.interfaces.repositories.user_repository import IUserRepository
from app.domain.entities.user import UserEntity
from app.infrastructure.db.models import UserModel

class SqlAlchemyUserRepository(IUserRepository):
    def __init__(self, db_session: Session):
        self.db = db_session

    def get_by_username(self, username: str) -> Optional[UserEntity]:
        # 1. Truy vấn Database bằng ORM Model
        db_user = self.db.query(UserModel).filter(UserModel.username == username).first()
        
        if not db_user:
            return None
            
        # 2. Thực hiện Mapping (Chuyển đổi từ Model sang Entity)
        return UserEntity(
            id=db_user.id,
            username=db_user.username,
            hashed_password=db_user.hashed_password,
            created_at=db_user.created_at
        )