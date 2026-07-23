from fastapi import APIRouter, Depends
from app.schemas.chat_dto import ChatRequest, ChatResponse
from app.application.chat.use_case import ChatUseCase
from app.infrastructure.llm.openai_client import OpenAIClient
from fastapi.responses import StreamingResponse
from app.core.security import get_current_user, oauth2_scheme
from sqlalchemy.orm import Session
from app.infrastructure.db.session import get_db

router = APIRouter()


def get_chat_use_case(db: Session = Depends(get_db)):
    # Build the OpenAI client here
    llm_provider = OpenAIClient(model="gpt-4o-mini", temperature=0.7)
    # Inject it into the use case
    return ChatUseCase(llm_provider=llm_provider, db=db)


@router.post("/", response_model=ChatResponse)
async def chat_with_farmmate(
    request: ChatRequest,
    chat_use_case: ChatUseCase = Depends(get_chat_use_case),
    current_user: dict = Depends(get_current_user),
    token: str = Depends(oauth2_scheme),
):
    """
    API to send a question to the agricultural AI assistant.
    The AI will automatically use the RAG skill to retrieve data when needed.
    """
    response = await chat_use_case.process_chat(request, current_user, token)
    return response


@router.post("/stream")
async def stream_chat_with_farmmate(
    request: ChatRequest,
    use_case: ChatUseCase = Depends(get_chat_use_case),
    current_user: dict = Depends(get_current_user),
    token: str = Depends(oauth2_scheme),
):
    """
    Streaming API: emits text incrementally using SSE.
    It does not use response_model because the response is a continuous stream.
    """
    return StreamingResponse(
        use_case.stream_chat(request, current_user, token),
        media_type="text/event-stream",  # Required format so browsers understand this is an SSE stream
    )


