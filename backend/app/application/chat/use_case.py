import time
import json
from app.schemas.chat_dto import ChatRequest, ChatResponse, ChatData, ResponseMetadata
from typing import AsyncGenerator
from app.agents.orchestrator import get_chat_agent, agent_shared_state
from app.application.chat.response_enhancer import ResponseEnhancer
from app.domain.interfaces.llm_provider import ILLMProvider
from app.domain.interfaces.llm_provider import ILLMProvider
from app.infrastructure.api.aaem_client import AAEMClient
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

    async def process_chat(self, request: ChatRequest, current_user=None, token: str = None) -> ChatResponse:
        """Handle the main chat flow with full metadata."""
        try:
            start_time = time.time()

            bot_answer, skill_result = self._invoke_agent(request.query, token, current_user)

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
            print(f"Chat use case error: {e}")
            return self._build_error_response(
                session_id=request.session_id, start_time=start_time
            )

    def _invoke_agent(self, query: str, token: str = None, current_user=None):
        """Reset the cache and call the agent to process the question (synchronous flow)."""

        # 1. CREATE A REQUEST-SPECIFIC STATE CONTAINER
        my_state = {}
        if token:
            my_state["access_token"] = token
        agent_shared_state.set(my_state)
        
        user_context_text = "No station information available."
        if token:
            aaem_client = AAEMClient()
            stations = aaem_client.fetch_all_user_stations(token)
            user_context_text = f"This user owns {len(stations)} monitoring stations:\n"
            for st in stations:
                user_context_text += f"- Station '{st.get('name', 'Unknown')}' (ID: {st.get('stationId', 'Unknown')}).\n"

        # 2. Run the agent
        result = self.agent.invoke(
            {"input": query, "chat_history": [], "user_context": user_context_text}
        )
        bot_answer = result.get("output", "Sorry, I cannot answer at the moment.")

        # 3. RETRIEVE THE RESULT FROM THE STATE CONTAINER AFTER THE TOOL HAS FINISHED
        skill_result = my_state.get("skill_result")

        # (Đã xóa bỏ hoàn toàn vòng lặp tìm intermediate_steps cũ rườm rà)

        return bot_answer, skill_result

    def _extract_metadata(self, bot_answer: str, skill_result: any):
        """Extract and map data from the skill result."""

        # If skill_result is empty, return empty arrays immediately
        if not skill_result:
            return [], [], None

        agent_actions = getattr(skill_result, "agent_actions", [])
        skill_tokens = getattr(skill_result, "tokens_used", None)

        # Lấy sources gốc từ skill_result.metadata
        raw_sources = (
            skill_result.metadata.get("sources", []) if skill_result.metadata else []
        )

        # Note: if response_enhancer.extract_sources fails,
        # fall back to the raw sources for debugging.
        try:
            sources = self.response_enhancer.extract_sources(
                skill_result_metadata=skill_result.metadata,
                answer=bot_answer,
                skill_name=skill_result.skill_name,
            )
        except Exception as e:
            print(f"Source extraction error: {e}")
            # If ResponseEnhancer fails, use the raw source list directly
            sources = raw_sources

        return sources, agent_actions, skill_tokens

    async def _generate_suggestions(self, answer: str, query: str, sources: list):
        """Generate suggested questions and fail gracefully so the main flow is not interrupted."""

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
            # Note: suggested question token usage may be captured depending on the LLM provider setup.
            # This is currently simplified and can be improved later.
            suggested_questions_tokens = None
            return suggested_questions, suggested_questions_tokens
        except Exception as e:
            print(f"Error generating suggested questions: {e}")
            # Fallback: no suggested questions, but the response still continues
            return [], None

    def _build_success_response(
        self,
        session_id: str,
        answer: str,
        sources: list,
        suggested_questions: list,
        metadata: dict,
    ) -> ChatResponse:
        """Build the success response payload."""
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
        """Build the error response payload."""
        return ChatResponse(
            status="error",
            data=ChatData(
                session_id=session_id,
                answer="A system error occurred while processing your request.",
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
        self, request: ChatRequest, current_user, token: str = None
    ) -> AsyncGenerator[str, None]:
        start_time = time.time()
        bot_answer = ""
        is_inside_tool = False

        my_state = {}
        if token:
            my_state["access_token"] = token
        agent_shared_state.set(my_state)

        try:
            # =======================================================
            # PHASE 1: HANDLE CONVERSATION STATE
            # =======================================================
            conversation_id = request.session_id

            if not conversation_id:
                # CASE 1: Start a new chat -> the backend generates the ID
                new_conv = ConversationModel(
                    id=str(uuid.uuid4()),
                    user_id=current_user.id,
                    title=request.query[:50],  # Lấy 50 ký tự đầu làm tiêu đề tạm
                )
                self.db.add(new_conv)
                self.db.commit()
                conversation_id = new_conv.id
            else:
                # CASE 2: The frontend sends a session_id -> it must exist and belong to the current user
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
                    # If the frontend sends an invalid ID or an ID belonging to another user, reject it immediately
                    raise HTTPException(
                        status_code=404,
                        detail="The session ID is invalid or you do not have permission to access this conversation.",
                    )

            # =======================================================
            # PHASE 1.5: LOAD CHAT HISTORY FROM THE DATABASE
            # =======================================================
            # Load the 10 most recent messages to avoid sending too much context to the LLM
            past_messages = (
                self.db.query(MessageModel)
                .filter(MessageModel.conversation_id == conversation_id)
                .order_by(MessageModel.created_at.desc())
                .limit(10)
                .all()
            )

            # Reverse the list to return it in chronological order (old -> new)
            past_messages.reverse()

            # Convert the database models into LangChain message objects
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
            # Thay vì hardcode, gọi AAEM API lấy trạm thật
            user_context_text = "No station information available."
            if token:
                try:
                    aaem_client = AAEMClient()
                    stations = aaem_client.fetch_all_user_stations(token)
                    user_context_text = f"This user owns {len(stations)} monitoring stations:\n"
                    for st in stations:
                        user_context_text += f"- Station '{st.get('name', 'Unknown')}' (ID: {st.get('stationId', 'Unknown')}).\n"
                except Exception as e:
                    if hasattr(e, 'response') and e.response is not None and e.response.status_code == 401:
                        yield f"data: {json.dumps({'event': 'error', 'code': 401, 'message': 'Unauthorized'})}\n\n"
                        return
                    else:
                        print(f"Error fetching stations: {e}")

            yield f"data: {json.dumps({'event': 'status', 'message': 'Analyzing your question...'})}\n\n"

            async for event in self.agent.astream_events(
                {
                    "input": request.query,
                    "chat_history": chat_history,  # Sau này bạn có thể query DB để nhét lịch sử chat vào đây
                    "user_context": user_context_text,
                },
                version="v2",
            ):
                kind = event["event"]

                if kind == "on_chain_start" and event.get("name") in ["router", "data_gatherer", "rag"]:
                    is_inside_tool = True
                    node_name = event.get("name")
                    if node_name == "router":
                        action_msg = "Phân tích yêu cầu (Routing)..."
                    elif node_name == "data_gatherer":
                        action_msg = "Thu thập dữ liệu trạm/mùa vụ..."
                    else:
                        action_msg = "Tra cứu tài liệu kỹ thuật (RAG)..."
                    yield f"data: {json.dumps({'event': 'status', 'message': action_msg})}\n\n"

                elif kind == "on_chain_end" and event.get("name") in ["router", "data_gatherer", "rag"]:
                    is_inside_tool = False
                    yield f"data: {json.dumps({'event': 'status', 'message': 'Đã hoàn tất xử lý, đang tổng hợp...'})}\n\n"
                    
                # Vẫn giữ lại on_tool_start nếu sau này dùng AgentExecutor bên trong Node
                elif kind == "on_tool_start":
                    is_inside_tool = True
                    tool_name = event.get("name", "công cụ")
                    yield f"data: {json.dumps({'event': 'status', 'message': f'Looking up ({tool_name})...'})}\n\n"

                elif kind == "on_tool_end":
                    is_inside_tool = False
                    yield f"data: {json.dumps({'event': 'status', 'message': 'Data gathered, synthesizing response...'})}\n\n"

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


