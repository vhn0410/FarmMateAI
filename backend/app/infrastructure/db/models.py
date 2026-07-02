import uuid
import datetime
from sqlalchemy import Column, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()

class UserModel(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    email = Column(String, nullable=True)
    full_name = Column(String, nullable=True)
    auth_provider = Column(String, default="postgres") # Lưu vết: 'postgres' hoặc 'keycloak'
    role = Column(String, default="user", nullable=False) # 'user' or 'admin'
    
    # Quan hệ 1-N sang Conversations
    conversations = relationship("ConversationModel", back_populates="owner", cascade="all, delete-orphan")


class ConversationModel(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    owner = relationship("UserModel", back_populates="conversations")
    # Quan hệ 1-N sang Messages
    messages = relationship("MessageModel", back_populates="conversation", cascade="all, delete-orphan")


class MessageModel(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    sender_type = Column(String, nullable=False)  # "user" hoặc "ai"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    conversation = relationship("ConversationModel", back_populates="messages")