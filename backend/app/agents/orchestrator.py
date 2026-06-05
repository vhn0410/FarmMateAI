from langchain_classic.agents.agent_types import AgentType
from langchain_classic.agents.initialize import initialize_agent
from langchain_core.tools import Tool
from app.agents.skills.rag_agriculture.tool import AgricultureRAGSkill
from app.infrastructure.vector_store.pgvector_provider import PGVectorProvider
from app.infrastructure.llm.openai_client import OpenAIClient


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
    tools = [
        Tool(name=rag_skill.name, func=rag_skill.run, description=rag_skill.description)
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
