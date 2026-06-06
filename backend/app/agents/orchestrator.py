from langchain_classic.agents.agent_types import AgentType
from langchain_classic.agents.initialize import initialize_agent
from langchain_core.tools import Tool
from app.agents.skills.rag_agriculture.tool import AgricultureRAGSkill
from app.agents.skills.base import SkillResult
from app.infrastructure.vector_store.pgvector_provider import PGVectorProvider
from app.infrastructure.llm.openai_client import OpenAIClient
from typing import Optional, Dict


# Global storage để lưu SkillResult từ các skills
# Dùng để sau khi Agent execute xong, use_case có thể lấy metadata từ đây
_skill_results_cache: Dict[str, SkillResult] = {}


def _create_tool_wrapper(skill):
    """
    Tạo wrapper cho skill.run() để:
    1. Call skill.run() nhận SkillResult
    2. Store SkillResult trong global cache
    3. Trả về string cho Agent (vì Agent chỉ expect string từ tools)
    """

    def tool_func(query: str) -> str:
        result: SkillResult = skill.run(query)
        # Store SkillResult để use_case lấy sau này
        _skill_results_cache[skill.name] = result
        # Trả về string cho Agent
        return result.answer

    return tool_func


def get_chat_agent():
    """Khởi tạo và cấu hình AI Agent với các kỹ năng (Skills)."""

    # 1. Khởi tạo mô hình ngôn ngữ
    llm = OpenAIClient(model="gpt-4o-mini", temperature=0.0).get_llm()

    # 2. Khởi tạo Vector Store Provider
    vector_store_provider = PGVectorProvider()

    # 3. Khởi tạo các kỹ năng với Dependency Injection
    rag_skill = AgricultureRAGSkill(
        vector_store_provider=vector_store_provider,
        llm_provider=OpenAIClient(model="gpt-4o-mini", temperature=0.0),
    )

    # 4. Đóng gói thành danh sách Tools cho Agent
    # Sử dụng wrapper để intercept SkillResult và store vào cache
    tools = [
        Tool(
            name=rag_skill.name,
            func=_create_tool_wrapper(rag_skill),
            description=rag_skill.description,
        )
    ]

    # 5. Khởi tạo Agent (Sử dụng ReAct framework)
    agent = initialize_agent(
        tools=tools,
        llm=llm,
        agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION,
        verbose=True,  # Bật True để xem log Agent "suy nghĩ" trong Terminal
        handle_parsing_errors=True,
    )

    return agent


def get_last_skill_result(skill_name: str = "Tu_van_ky_thuat_nong_nghiep") -> Optional[SkillResult]:
    """
    Lấy SkillResult từ cache sau khi Agent execution.
    Dùng trong use_case để lấy metadata (sources, tokens, actions).
    """
    return _skill_results_cache.get(skill_name)


def clear_skill_cache():
    """Xóa cache SkillResult (gọi khi bắt đầu session mới)."""
    global _skill_results_cache
    _skill_results_cache.clear()
