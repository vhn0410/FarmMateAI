from fastapi import APIRouter, Depends
from app.schemas.chat_dto import ChatRequest, ChatResponse
from app.application.chat.use_case import ChatUseCase
from app.infrastructure.llm.openai_client import OpenAIClient
from fastapi.responses import StreamingResponse
from app.core.security import get_current_user
from sqlalchemy.orm import Session
from app.infrastructure.db.session import get_db

router = APIRouter()


def get_chat_use_case(db: Session = Depends(get_db)):
    # Lắp ráp OpenAI Client ở đây
    llm_provider = OpenAIClient(model="gpt-4o-mini", temperature=0.7)
    # Tiêm vào Use Case
    return ChatUseCase(llm_provider=llm_provider, db=db)


@router.post("/", response_model=ChatResponse)
async def chat_with_farmmate(
    request: ChatRequest,
    chat_use_case: ChatUseCase = Depends(get_chat_use_case),
    current_user: dict = Depends(get_current_user),
):
    """
    API gửi câu hỏi cho AI Nông nghiệp.
    AI sẽ tự động dùng RAG Skill để tra cứu dữ liệu nếu cần.
    """
    response = await chat_use_case.process_chat(request)
    return response


@router.post("/stream")
async def stream_chat_with_farmmate(
    request: ChatRequest,
    use_case: ChatUseCase = Depends(get_chat_use_case),
    current_user: dict = Depends(get_current_user),
):
    """
    API Streaming: Trả về từng chữ (SSE).
    Không dùng response_model vì dữ liệu là luồng liên tục.
    """
    return StreamingResponse(
        use_case.stream_chat(request, current_user),
        media_type="text/event-stream",  # Định dạng bắt buộc để trình duyệt hiểu đây là luồng SSE
    )
