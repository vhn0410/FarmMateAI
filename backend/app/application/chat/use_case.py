import time
from app.schemas.chat_dto import ChatRequest, ChatResponse, ChatData, ResponseMetadata
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
                bot_answer, skill_result
            )

            (
                suggested_questions,
                suggested_questions_tokens,
            ) = await self._generate_suggestions(bot_answer, request.query, sources)

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
