from fastapi import APIRouter, Depends
from app.schemas.chat_dto import ChatRequest
from app.application.knowledge.use_case import KnowledgeChatUseCase
from app.infrastructure.llm.openai_client import OpenAIClient
from fastapi.responses import StreamingResponse
from app.core.security import get_current_user, oauth2_scheme

router = APIRouter()

def get_knowledge_chat_use_case():
    llm_provider = OpenAIClient(model="gpt-4o-mini", temperature=0.0)
    return KnowledgeChatUseCase(llm_provider=llm_provider)

@router.post("/stream")
async def stream_document_chat(
    request: ChatRequest,
    use_case: KnowledgeChatUseCase = Depends(get_knowledge_chat_use_case),
    current_user: dict = Depends(get_current_user),
    token: str = Depends(oauth2_scheme),
):
    """
    API Streaming dành riêng cho RAG trên tài liệu cụ thể.
    Bỏ qua Agent, chỉ dùng LCEL RetrivalQA.
    """
    return StreamingResponse(
        use_case.stream_document_chat(request, current_user, token),
        media_type="text/event-stream",
    )
