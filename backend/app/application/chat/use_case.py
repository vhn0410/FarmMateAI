from app.schemas.chat_dto import ChatRequest, ChatResponse
from app.agents.orchestrator import get_chat_agent


class ChatUseCase:
    def __init__(self):
        # Khởi tạo Agent một lần để tái sử dụng
        self.agent = get_chat_agent()

    async def process_chat(self, request: ChatRequest) -> ChatResponse:
        """Xử lý luồng chat chính."""
        try:
            # Truyền câu hỏi vào Agent
            # Note: Do đang dùng CHAT_CONVERSATIONAL_REACT_DESCRIPTION,
            # Langchain thường yêu cầu input là chuỗi cho parameter 'input'
            result = self.agent.invoke({"input": request.query, "chat_history": []})

            # Lấy câu trả lời từ output của Agent
            bot_answer = result.get("output", "Xin lỗi, tôi không thể trả lời lúc này.")

            return ChatResponse(answer=bot_answer, session_id=request.session_id)
        except Exception as e:
            print(f"Lỗi Use Case Chat: {e}")
            return ChatResponse(
                answer="Đã có lỗi hệ thống xảy ra khi xử lý câu hỏi của bạn.",
                session_id=request.session_id,
            )
