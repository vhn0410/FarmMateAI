from abc import ABC, abstractmethod
from typing import Optional
from app.domain.entities.user import UserEntity

class IUserRepository(ABC):
    @abstractmethod
    def get_by_username(self, username: str) -> Optional[UserEntity]:
        pass

    @abstractmethod
    def create_user(self, user_data: dict) -> UserEntity:
        pass