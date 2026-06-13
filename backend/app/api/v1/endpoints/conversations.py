from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.infrastructure.db.session import get_db
from app.core.security import get_current_user
from app.infrastructure.db.models import UserModel, ConversationModel, MessageModel
from app.schemas.chat_dto import ConversationListResponse, ConversationDetailResponse
from app.schemas.chat_dto import ConversationCreateRequest, ConversationCreateResponse
import uuid

router = APIRouter()


@router.get("/", response_model=ConversationListResponse)
def get_my_conversations(
    db: Session = Depends(get_db), current_user: UserModel = Depends(get_current_user)
):
    """
    Lấy danh sách tất cả các hội thoại của user đang đăng nhập.
    Sắp xếp theo thời gian tạo mới nhất lên đầu.
    """
    conversations = (
        db.query(ConversationModel)
        .filter(ConversationModel.user_id == current_user.id)
        .order_by(ConversationModel.created_at.desc())
        .all()
    )

    return {"status": "success", "data": conversations}


@router.get("/{conversation_id}/messages", response_model=ConversationDetailResponse)
def get_conversation_messages(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """
    Lấy toàn bộ tin nhắn bên trong một cuộc hội thoại.
    """
    # 1. Kiểm tra hội thoại có tồn tại và thuộc về user này không (Chống IDOR)
    conversation = (
        db.query(ConversationModel)
        .filter(
            ConversationModel.id == conversation_id,
            ConversationModel.user_id == current_user.id,
        )
        .first()
    )

    if not conversation:
        raise HTTPException(
            status_code=404,
            detail="Hội thoại không tồn tại hoặc bạn không có quyền truy cập.",
        )

    # 2. Lấy danh sách tin nhắn, sắp xếp theo thời gian cũ -> mới
    messages = (
        db.query(MessageModel)
        .filter(MessageModel.conversation_id == conversation_id)
        .order_by(MessageModel.created_at.asc())
        .all()
    )

    return {
        "status": "success",
        "conversation_id": conversation_id,
        "messages": messages,
    }


@router.post("/", response_model=ConversationCreateResponse)
def create_conversation(
    request: ConversationCreateRequest,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """
    Tạo một cuộc hội thoại mới.
    Thường được gọi khi user bấm nút "New Chat" trên giao diện.
    """
    new_conv = ConversationModel(
        id=str(uuid.uuid4()), user_id=current_user.id, title=request.title
    )

    db.add(new_conv)
    db.commit()
    db.refresh(new_conv)

    return {"status": "success", "data": new_conv}
