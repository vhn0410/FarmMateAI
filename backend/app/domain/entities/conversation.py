from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
from app.domain.entities.message import MessageEntity

@dataclass
class ConversationEntity:
    id: str
    user_id: str
    title: Optional[str]
    created_at: datetime
    messages: List[MessageEntity] = field(default_factory=list)