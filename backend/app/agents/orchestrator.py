import contextvars
from langchain_classic.agents.openai_tools.base import create_openai_tools_agent
from langchain_classic.agents.agent import AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool

from app.agents.skills.rag_agriculture.tool import AgricultureRAGSkill
from app.agents.skills.base import SkillResult
from app.infrastructure.vector_store.pgvector_provider import PGVectorProvider
from app.infrastructure.llm.openai_client import OpenAIClient


agent_shared_state = contextvars.ContextVar("agent_shared_state")


def get_chat_agent():
    llm = OpenAIClient(model="gpt-4o-mini", temperature=0.0, streaming=True).get_llm()
    vector_store_provider = PGVectorProvider()

    rag_skill = AgricultureRAGSkill(
        vector_store_provider=vector_store_provider,
        llm_provider=OpenAIClient(model="gpt-4o-mini", temperature=0.0),
    )

    @tool(rag_skill.name)
    def agriculture_tool(query: str) -> str:
        """Sử dụng công cụ này để tra cứu kiến thức nông nghiệp, tài liệu, số liệu môi trường đất và quy trình canh tác."""
        result: SkillResult = rag_skill.run(query)

        # Lấy kho chứa của User hiện tại ra và bỏ kết quả vào
        try:
            state = agent_shared_state.get()
            state["skill_result"] = result
        except LookupError:
            pass  # An toàn bỏ qua nếu test ngoài FastAPI

        return result.answer

    tools = [agriculture_tool]

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Bạn là kỹ sư tư vấn nông nghiệp FarmMate. Hãy luôn ưu tiên dùng công cụ '{tool_name}' để lấy thông tin thực tế trước khi trả lời. Trả lời súc tích và trực tiếp.",
            ),
            MessagesPlaceholder(variable_name="chat_history"),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    ).partial(tool_name=rag_skill.name)

    agent = create_openai_tools_agent(llm, tools, prompt)

    agent_executor = AgentExecutor(
        agent=agent, tools=tools, verbose=True, return_intermediate_steps=True
    )

    return agent_executor
