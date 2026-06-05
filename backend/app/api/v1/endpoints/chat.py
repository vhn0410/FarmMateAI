from fastapi import APIRouter
from app.schemas.chat_dto import ChatRequest, ChatResponse
from app.application.chat.use_case import ChatUseCase

router = APIRouter()
chat_use_case = ChatUseCase()


@router.post("/", response_model=ChatResponse)
async def chat_with_farmmate(request: ChatRequest):
    """
    API gửi câu hỏi cho AI Nông nghiệp.
    AI sẽ tự động dùng RAG Skill để tra cứu dữ liệu nếu cần.
    """
    response = await chat_use_case.process_chat(request)
    return response
