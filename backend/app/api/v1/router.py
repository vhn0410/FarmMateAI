from fastapi import APIRouter, Depends
from app.api.v1.endpoints import documents
from app.api.v1.endpoints import chat
from app.api.v1.endpoints import chat_documents
from app.api.v1.endpoints import auth
from app.api.v1.endpoints import user
from app.api.v1.endpoints import conversations

from app.core.security import get_admin_user

# Khởi tạo router tổng cho phiên bản 1 (v1)
api_router = APIRouter()

# Gắn ống nước: Nối router của file documents.py vào router tổng
# Tiền tố (prefix) ở đây là /documents
# Yêu cầu quyền admin cho tất cả các API trong documents
api_router.include_router(
    documents.router, 
    prefix="/documents", 
    tags=["Knowledge Base"],
    dependencies=[Depends(get_admin_user)]
)

# Gắn ống nước cho Chat (Tạm thời đóng)
api_router.include_router(chat.router, prefix="/chat", tags=["Chatbot"])
api_router.include_router(chat_documents.router, prefix="/chat/document", tags=["Document Chat"])
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(user.router, prefix="/users", tags=["Authentication"])
api_router.include_router(conversations.router, prefix="/conversations", tags=["Conversations"])
