import time
import json
from app.schemas.chat_dto import ChatRequest, ChatResponse, ChatData, ResponseMetadata
from typing import AsyncGenerator
from app.agents.orchestrator import get_chat_agent, agent_shared_state
from app.application.chat.response_enhancer import ResponseEnhancer
from app.domain.interfaces.llm_provider import ILLMProvider
from app.agents.mocks.mock_system import MOCK_SYSTEM_DB
import uuid
from app.infrastructure.db.models import MessageModel, ConversationModel
from sqlalchemy.orm import Session
from fastapi import HTTPException
from langchain_core.messages.human import HumanMessage
from langchain_core.messages.ai import AIMessage


class ChatUseCase:
    def __init__(self, llm_provider: ILLMProvider, db: Session):
        self.agent = get_chat_agent()
        self.response_enhancer = ResponseEnhancer()
        self.llm_provider = llm_provider
        self.db = db

    async def process_chat(self, request: ChatRequest) -> ChatResponse:
        """Xử lý luồng chat chính với đầy đủ metadata."""
        try:
            start_time = time.time()

            bot_answer, skill_result = self._invoke_agent(request.query)

            sources, agent_actions, skill_tokens = self._extract_metadata(
                bot_answer=bot_answer, skill_result=skill_result
            )

            (
                suggested_questions,
                suggested_questions_tokens,
            ) = await self._generate_suggestions(
                answer=bot_answer, query=request.query, sources=sources
            )

            tokens_used = self.response_enhancer.aggregate_tokens(
                skill_tokens=skill_tokens,
                suggested_questions_tokens=suggested_questions_tokens,
            )

            return self._build_success_response(
                session_id=request.session_id,
                answer=bot_answer,
                sources=sources,
                suggested_questions=suggested_questions,
                metadata={
                    "tokens_used": tokens_used,
                    "agent_actions": agent_actions,
                    "start_time": start_time,
                },
            )

        except Exception as e:
            print(f"Lỗi Use Case Chat: {e}")
            return self._build_error_response(
                session_id=request.session_id, start_time=start_time
            )

    def _invoke_agent(self, query: str):
        """Reset cache và gọi Agent xử lý câu hỏi (Luồng đồng bộ)."""

        # 1. TẠO CHIẾC HỘP RIÊNG CHO REQUEST NÀY
        my_state = {}
        agent_shared_state.set(my_state)

        # 2. Gọi Agent chạy
        result = self.agent.invoke(
            {"input": query, "chat_history": [], "user_context": []}
        )
        bot_answer = result.get("output", "Xin lỗi, tôi không thể trả lời lúc này.")

        # 3. LẤY KẾT QUẢ TỪ CHIẾC HỘP SAU KHI TOOL CHẠY XONG
        skill_result = my_state.get("skill_result")

        # (Đã xóa bỏ hoàn toàn vòng lặp tìm intermediate_steps cũ rườm rà)

        return bot_answer, skill_result

    def _extract_metadata(self, bot_answer: str, skill_result: any):
        """Trích xuất và mapping dữ liệu từ kết quả của Skill."""

        # Nếu skill_result bị rỗng, lập tức trả về mảng rỗng
        if not skill_result:
            return [], [], None

        agent_actions = getattr(skill_result, "agent_actions", [])
        skill_tokens = getattr(skill_result, "tokens_used", None)

        # Lấy sources gốc từ skill_result.metadata
        raw_sources = (
            skill_result.metadata.get("sources", []) if skill_result.metadata else []
        )

        # CHÚ Ý: Nếu hàm extract_sources của response_enhancer bị lỗi,
        # hãy thử trả về trực tiếp raw_sources ở đây để debug.
        try:
            sources = self.response_enhancer.extract_sources(
                skill_result_metadata=skill_result.metadata,
                answer=bot_answer,
                skill_name=skill_result.skill_name,
            )
        except Exception as e:
            print(f"Lỗi extract sources: {e}")
            # Nếu ResponseEnhancer lỗi, lấy luôn danh sách sources thô
            sources = raw_sources

        return sources, agent_actions, skill_tokens

    async def _generate_suggestions(self, answer: str, query: str, sources: list):
        """Sinh câu hỏi gợi ý, tự động bắt lỗi để không làm gián đoạn luồng chính"""

        suggested_questions = []
        suggested_questions_tokens = None
        try:
            suggested_questions = (
                await self.response_enhancer.generate_suggested_questions(
                    answer=answer,
                    query=query,
                    sources=sources,
                    llm_provider=self.llm_provider,
                )
            )
            # Note: Token usage từ suggested questions có thể capture tùy LLM provider setup
            # Hiện tại simplified, sẽ improve sau
            suggested_questions_tokens = None
            return suggested_questions, suggested_questions_tokens
        except Exception as e:
            print(f"Error generating suggested questions: {e}")
            # Fallback: không có suggested questions nhưng response vẫn tiếp tục
            return [], None

    def _build_success_response(
        self,
        session_id: str,
        answer: str,
        sources: list,
        suggested_questions: list,
        metadata: dict,
    ) -> ChatResponse:
        """Đóng gói JSON cho trường hợp thành công."""
        return ChatResponse(
            status="success",
            data=ChatData(
                session_id=session_id,
                answer=answer,
                sources=sources,
                suggested_questions=suggested_questions,
            ),
            metadata=ResponseMetadata(
                processing_time_ms=int(
                    (time.time() - metadata.get("start_time", time.time())) * 1000
                ),
                tokens_used=metadata.get("tokens_used"),
                agent_actions=metadata.get("agent_actions"),
            ),
        )

    def _build_error_response(self, session_id: str, start_time: float) -> ChatResponse:
        """Đóng gói JSON cho trường hợp lỗi."""
        return ChatResponse(
            status="error",
            data=ChatData(
                session_id=session_id,
                answer="Đã có lỗi hệ thống xảy ra khi xử lý câu hỏi của bạn.",
                sources=[],
                suggested_questions=[],
            ),
            metadata=ResponseMetadata(
                processing_time_ms=int((time.time() - start_time) * 1000),
                tokens_used=None,
                agent_actions=[],
            ),
        )

    async def stream_chat(
        self, request: ChatRequest, current_user
    ) -> AsyncGenerator[str, None]:
        start_time = time.time()
        bot_answer = ""
        is_inside_tool = False

        my_state = {}
        agent_shared_state.set(my_state)

        try:
            # =======================================================
            # PHASE 1: XỬ LÝ CONVERSATION (HỘI THOẠI)
            # =======================================================
            conversation_id = request.session_id

            if not conversation_id:
                # TRƯỜNG HỢP 1: Bắt đầu chat mới -> Backend TỰ SINH ID
                new_conv = ConversationModel(
                    id=str(uuid.uuid4()),
                    user_id=current_user.id,
                    title=request.query[:50],  # Lấy 50 ký tự đầu làm tiêu đề tạm
                )
                self.db.add(new_conv)
                self.db.commit()
                conversation_id = new_conv.id
            else:
                # TRƯỜNG HỢP 2: FE gửi session_id lên -> Bắt buộc phải TỒN TẠI và ĐÚNG CHỦ SỞ HỮU
                conv = (
                    self.db.query(ConversationModel)
                    .filter(
                        ConversationModel.id == conversation_id,
                        ConversationModel.user_id
                        == current_user.id,  # Cực kỳ quan trọng: Ngăn lỗi IDOR
                    )
                    .first()
                )

                if not conv:
                    # Nếu FE gửi ID bậy bạ, hoặc ID của người khác -> Quăng lỗi ngay!
                    raise HTTPException(
                        status_code=404,
                        detail="Session ID không hợp lệ hoặc bạn không có quyền truy cập hội thoại này.",
                    )

            # =======================================================
            # PHASE 1.5: LẤY LỊCH SỬ CHAT TỪ DATABASE
            # =======================================================
            # Lấy 10 tin nhắn gần nhất (tránh lấy quá nhiều làm tràn Token của LLM)
            past_messages = (
                self.db.query(MessageModel)
                .filter(MessageModel.conversation_id == conversation_id)
                .order_by(MessageModel.created_at.desc())
                .limit(10)
                .all()
            )

            # Đảo ngược list để trả về đúng thứ tự thời gian (cũ -> mới)
            past_messages.reverse()

            # Chuyển đổi Model Database sang định dạng của LangChain
            chat_history = []
            for msg in past_messages:
                if msg.sender_type == "user":
                    chat_history.append(HumanMessage(content=msg.content))
                elif msg.sender_type == "ai":
                    chat_history.append(AIMessage(content=msg.content))

            # =======================================================
            # PHASE 2: LƯU CÂU HỎI CỦA USER
            # =======================================================
            user_msg = MessageModel(
                conversation_id=conversation_id,
                sender_type="user",
                content=request.query,
            )
            self.db.add(user_msg)
            self.db.commit()

            # =======================================================
            # PHASE 3: THỰC THI LUỒNG AGENT LANGGRAPH
            # =======================================================
            # Sửa chỗ hardcode lúc trước thành ID thật của người đang đăng nhập
            current_user_id = current_user.id
            user_stations = MOCK_SYSTEM_DB.get(current_user_id, [])

            user_context_text = (
                f"Người dùng này sở hữu {len(user_stations)} trạm quan trắc:\n"
            )
            for st in user_stations:
                user_context_text += f"- Trạm '{st['station_name']}' (ID: {st['station_id']}), trồng {st['crop']}, nằm tại {st['location']}.\n"

            yield f"data: {json.dumps({'event': 'status', 'message': 'Đang phân tích câu hỏi...'})}\n\n"

            async for event in self.agent.astream_events(
                {
                    "input": request.query,
                    "chat_history": chat_history,  # Sau này bạn có thể query DB để nhét lịch sử chat vào đây
                    "user_context": user_context_text,
                },
                version="v2",
            ):
                kind = event["event"]

                if kind == "on_tool_start":
                    is_inside_tool = True
                    tool_name = event.get("name", "công cụ")
                    yield f"data: {json.dumps({'event': 'status', 'message': f'Đang tra cứu ({tool_name})...'})}\n\n"

                elif kind == "on_tool_end":
                    is_inside_tool = False
                    yield f"data: {json.dumps({'event': 'status', 'message': 'Đã thu thập dữ liệu, đang tổng hợp câu trả lời...'})}\n\n"

                elif kind == "on_chat_model_stream":
                    if not is_inside_tool:
                        chunk = event["data"]["chunk"]
                        if chunk.content and isinstance(chunk.content, str):
                            token = chunk.content
                            bot_answer += token
                            yield f"data: {json.dumps({'event': 'token', 'text': token})}\n\n"

            # =======================================================
            # PHASE 4: LƯU CÂU TRẢ LỜI CỦA AI VÀ TRẢ VỀ METADATA
            # =======================================================
            ai_msg = MessageModel(
                conversation_id=conversation_id, sender_type="ai", content=bot_answer
            )
            self.db.add(ai_msg)
            self.db.commit()

            skill_result = my_state.get("skill_result")

            sources, agent_actions, skill_tokens = self._extract_metadata(
                bot_answer=bot_answer, skill_result=skill_result
            )
            (
                suggested_questions,
                suggested_questions_tokens,
            ) = await self._generate_suggestions(
                answer=bot_answer, query=request.query, sources=sources
            )
            tokens_used = self.response_enhancer.aggregate_tokens(
                skill_tokens=skill_tokens,
                suggested_questions_tokens=suggested_questions_tokens,
            )

            final_metadata = {
                "event": "done",
                "session_id": conversation_id,  # Đảm bảo trả về ID mới nhất
                "sources": [s.model_dump() for s in sources] if sources else [],
                "suggested_questions": suggested_questions,
                "metadata": {
                    "processing_time_ms": int((time.time() - start_time) * 1000),
                    "tokens_used": tokens_used.model_dump() if tokens_used else None,
                    "agent_actions": agent_actions,
                },
            }
            yield f"data: {json.dumps(final_metadata)}\n\n"

        except Exception as e:
            print(f"[Lỗi Streaming]: {e}")
            error_data = {"event": "error", "message": f"Hệ thống gặp sự cố: {str(e)}"}
            yield f"data: {json.dumps(error_data)}\n\n"
