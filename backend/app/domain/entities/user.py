from dataclasses import dataclass
from datetime import datetime

@dataclass
class UserEntity:
    id: str
    username: str
    hashed_password: str
    created_at: datetime