import time
from app.schemas.chat_dto import ChatRequest, ChatResponse, ChatData, ResponseMetadata
from app.agents.orchestrator import get_chat_agent, get_last_skill_result, clear_skill_cache
from app.application.chat.response_enhancer import ResponseEnhancer
from app.domain.interfaces.llm_provider import ILLMProvider

class ChatUseCase:
    def __init__(self, llm_provider: ILLMProvider):
        # Khởi tạo Agent một lần để tái sử dụng
        self.agent = get_chat_agent()
        self.response_enhancer = ResponseEnhancer()
        self.llm_provider = llm_provider

    async def process_chat(self, request: ChatRequest) -> ChatResponse:
        """Xử lý luồng chat chính với đầy đủ metadata."""
        try:
            start_time = time.time()

            # ===== STEP 1: Clear cache từ session trước =====
            clear_skill_cache()

            # ===== STEP 2: Invoke Agent =====
            # Note: Tool wrapper sẽ store SkillResult vào cache
            result = self.agent.invoke({"input": request.query, "chat_history": []})
            bot_answer = result.get("output", "Xin lỗi, tôi không thể trả lời lúc này.")

            # ===== STEP 3: Lấy SkillResult từ cache =====
            skill_result = get_last_skill_result()

            # ===== STEP 4: Extract Sources từ SkillResult metadata =====
            sources = []
            agent_actions = []
            skill_tokens = None

            if skill_result:
                agent_actions = skill_result.agent_actions or []
                skill_tokens = skill_result.tokens_used

                sources = self.response_enhancer.extract_sources(
                    skill_result_metadata=skill_result.metadata,
                    answer=bot_answer,
                    skill_name=skill_result.skill_name,
                )

            # ===== STEP 5: Generate Suggested Questions =====
            suggested_questions = []
            suggested_questions_tokens = None
            try:
                suggested_questions = await self.response_enhancer.generate_suggested_questions(
                    answer=bot_answer,
                    query=request.query,
                    sources=sources,
                    llm_provider=self.llm_provider,
                )
                # Note: Token usage từ suggested questions có thể capture tùy LLM provider setup
                # Hiện tại simplified, sẽ improve sau
                suggested_questions_tokens = None
            except Exception as e:
                print(f"Error generating suggested questions: {e}")
                # Fallback: không có suggested questions nhưng response vẫn tiếp tục
                suggested_questions = []

            # ===== STEP 6: Aggregate Tokens =====
            tokens_used = self.response_enhancer.aggregate_tokens(
                skill_tokens=skill_tokens,
                suggested_questions_tokens=suggested_questions_tokens,
            )

            # ===== STEP 7: Build Complete ChatResponse =====
            processing_time = int((time.time() - start_time) * 1000)

            return ChatResponse(
                status="success",
                data=ChatData(
                    session_id=request.session_id,
                    answer=bot_answer,
                    sources=sources,
                    suggested_questions=suggested_questions,
                ),
                metadata=ResponseMetadata(
                    processing_time_ms=processing_time,
                    tokens_used=tokens_used,
                    agent_actions=agent_actions,
                ),
            )

        except Exception as e:
            print(f"Lỗi Use Case Chat: {e}")
            processing_time = int((time.time() - start_time) * 1000)
            return ChatResponse(
                status="error",
                data=ChatData(
                    session_id=request.session_id,
                    answer="Đã có lỗi hệ thống xảy ra khi xử lý câu hỏi của bạn.",
                    sources=[],
                    suggested_questions=[],
                ),
                metadata=ResponseMetadata(
                    processing_time_ms=processing_time,
                    tokens_used=None,
                    agent_actions=[],
                ),
            )
