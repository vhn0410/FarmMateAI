import time
import json
from app.schemas.chat_dto import ChatRequest, ChatResponse, ChatData, ResponseMetadata
from typing import AsyncGenerator
from app.agents.orchestrator import (
    get_chat_agent,
    get_last_skill_result,
    clear_skill_cache,
)
from app.application.chat.response_enhancer import ResponseEnhancer
from app.domain.interfaces.llm_provider import ILLMProvider


class ChatUseCase:
    def __init__(self, llm_provider: ILLMProvider):
        self.agent = get_chat_agent()
        self.response_enhancer = ResponseEnhancer()
        self.llm_provider = llm_provider

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
        """Reset cache và gọi Agent xử lý câu hỏi."""
        clear_skill_cache()
        result = self.agent.invoke({"input": query, "chat_history": []})
        bot_answer = result.get("output", "Xin lỗi, tôi không thể trả lời lúc này.")
        skill_result = get_last_skill_result()

        return bot_answer, skill_result

    def _extract_metadata(self, bot_answer: str, skill_result: any):
        """Trích xuất và mapping dữ liệu từ kết quả của Skill."""

        if not skill_result:
            return [], [], None

        if skill_result:
            agent_actions = skill_result.agent_actions or []
            skill_tokens = skill_result.tokens_used

            sources = self.response_enhancer.extract_sources(
                skill_result_metadata=skill_result.metadata,
                answer=bot_answer,
                skill_name=skill_result.skill_name,
            )
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

    async def stream_chat(self, request: ChatRequest) -> AsyncGenerator[str, None]:
        """
        Hàm Generator: Bơm liên tục (yield) các mảnh dữ liệu (chunks) về cho Client bằng astream_events.
        """
        start_time = time.time()
        bot_answer = ""

        # Reset cache từ session trước
        clear_skill_cache()

        try:
            # 1. Gửi tín hiệu khởi tạo đầu tiên cho Frontend hiển thị UI Loading
            yield f"data: {json.dumps({'event': 'status', 'message': 'Đang phân tích câu hỏi...'})}\n\n"

            # 2. Mở luồng lắng nghe sự kiện từ LangChain Agent
            async for event in self.agent.astream_events(
                {"input": request.query, "chat_history": []}, version="v2"
            ):
                kind = event["event"]

                # [Sự kiện A]: Agent bắt đầu gọi công cụ RAG
                if kind == "on_tool_start":
                    tool_name = event.get("name", "công cụ")
                    yield f"data: {json.dumps({'event': 'status', 'message': f'Đang tra cứu tài liệu ({tool_name})...'})}\n\n"

                # [Sự kiện B]: Agent nhận được kết quả từ công cụ RAG
                elif kind == "on_tool_end":
                    # LƯU Ý: Không gọi get_last_skill_result() ở đây nữa để tránh race condition
                    yield f"data: {json.dumps({'event': 'status', 'message': 'Đã đọc tài liệu, đang tổng hợp câu trả lời...'})}\n\n"

                # [Sự kiện C]: LLM bắt đầu nhả từng chữ (Streaming Token)
                elif kind == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    if chunk.content and isinstance(chunk.content, str):
                        token = chunk.content
                        bot_answer += token  # Lưu lại để chấm điểm/sinh câu hỏi sau

                        # Bơm ngay lập tức token này về Frontend
                        yield f"data: {json.dumps({'event': 'token', 'text': token})}\n\n"

            # =========================================================
            # 3. KẾT THÚC STREAM -> XỬ LÝ HẬU KỲ (POST-PROCESSING)
            # =========================================================

            # Lấy Cache ở đây là an toàn nhất (sau khi mọi thứ đã chạy xong)
            skill_result = get_last_skill_result()

            # ĐÃ SỬA LỖI: Gọi đúng thứ tự tham số (bot_answer trước, skill_result sau)
            sources, agent_actions, skill_tokens = self._extract_metadata(
                bot_answer=bot_answer, skill_result=skill_result
            )

            # Sinh câu hỏi gợi ý
            (
                suggested_questions,
                suggested_questions_tokens,
            ) = await self._generate_suggestions(
                answer=bot_answer, query=request.query, sources=sources
            )

            # Gom token
            tokens_used = self.response_enhancer.aggregate_tokens(
                skill_tokens=skill_tokens,
                suggested_questions_tokens=suggested_questions_tokens,
            )

            # 4. GÓI TIN CHỐT HẠ (DONE): Gửi toàn bộ metadata
            final_metadata = {
                "event": "done",
                "session_id": request.session_id,
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
