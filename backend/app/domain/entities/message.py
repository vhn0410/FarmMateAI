from dataclasses import dataclass
from datetime import datetime

@dataclass
class MessageEntity:
    id: str
    conversation_id: str
    sender_type: str  # "user" hoặc "ai"
    content: str
    created_at: datetime