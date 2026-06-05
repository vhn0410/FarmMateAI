from fastapi import APIRouter
from app.api.v1.endpoints import documents
from app.api.v1.endpoints import chat

# Khởi tạo router tổng cho phiên bản 1 (v1)
api_router = APIRouter()

# Gắn ống nước: Nối router của file documents.py vào router tổng
# Tiền tố (prefix) ở đây là /documents
api_router.include_router(
    documents.router, prefix="/documents", tags=["Knowledge Base"]
)

# Gắn ống nước cho Chat (Tạm thời đóng)
api_router.include_router(chat.router, prefix="/chat", tags=["Chatbot"])
