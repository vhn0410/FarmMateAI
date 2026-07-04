import json
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from typing import Literal

from app.agents.workflow.state import AgentState
from app.infrastructure.llm.openai_client import OpenAIClient
from app.agents.skills.rag_agriculture.tool import AgricultureRAGSkill
from app.agents.skills.weather.tool import WeatherSkill
from app.agents.skills.progress_management.tool import ProgressManagementSkill
from app.agents.skills.iot_management.tool import IoTManagementSkill
from app.infrastructure.vector_store.pgvector_provider import PGVectorProvider

# Initialize Skills
vector_store_provider = PGVectorProvider()
rag_skill = AgricultureRAGSkill(
    vector_store_provider=vector_store_provider,
    llm_provider=OpenAIClient(model="gpt-4o", temperature=0.0),
)
weather_skill = WeatherSkill()
progress_skill = ProgressManagementSkill()
iot_skill = IoTManagementSkill()

llm_fast = OpenAIClient(model="gpt-4o-mini", temperature=0.0, streaming=False).get_llm()
llm_stream = OpenAIClient(model="gpt-4o", temperature=0.0, streaming=True).get_llm()


class RouterOutput(BaseModel):
    intent: Literal["FARMING_ADVICE", "DATA_CHECK", "GENERAL_KNOWLEDGE"] = Field(
        ..., description="The classified intent of the user's question."
    )
    station_id: str = Field(None, description="Extracted station ID if mentioned.")
    location: str = Field(None, description="Extracted location/city if mentioned.")
    project_name: str = Field(None, description="Extracted crop or project name if mentioned.")


class QueryFormulatorOutput(BaseModel):
    search_queries: list[str] = Field(..., description="A list of 1 to 3 concise, precise search queries formulated for the Vector Database.")



def router_node(state: AgentState):
    """Classifies the user query and extracts parameters."""
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a smart router for an agricultural AI.
        Analyze the user's input and classify the intent into ONE of these:
        - FARMING_ADVICE: The user needs advice, instructions, or asks 'what to do' about their farm.
        - DATA_CHECK: The user ONLY wants to check sensor/IoT/weather data, list their projects, or list their stations.
        - GENERAL_KNOWLEDGE: The user asks theoretical questions not tied to their specific farm.
        
        Also extract:
        - station_id: If they mention a specific station ID (numeric).
        - location: If they mention a city/province.
        - project_name: If they mention a specific crop like 'lua', 'ca', or a specific project name.
        
        User Context: {user_context}
        """),
        ("user", "{input}")
    ])
    
    chain = prompt | llm_fast.with_structured_output(RouterOutput)
    result = chain.invoke({"input": state["input"], "user_context": state["user_context"]})
    
    print("\n" + "="*50)
    print(f"[ROUTER NODE] Intent: {result.intent}")
    print(f"[ROUTER NODE] Extracted Station ID: {result.station_id}")
    print(f"[ROUTER NODE] Extracted Location: {result.location}")
    print(f"[ROUTER NODE] Extracted Project: {result.project_name}")
    print("="*50 + "\n")
    
    return {
        "intent": result.intent,
        "current_station_id": result.station_id,
        "current_location": result.location,
        "current_project": result.project_name
    }


def data_gatherer_node(state: AgentState):
    """Fetches data from IoT, PPM, and Weather APIs."""
    import contextvars
    from app.agents.orchestrator import agent_shared_state
    
    shared = agent_shared_state.get({})
    token = shared.get("access_token")
    
    iot_data = None
    ppm_data = None
    weather_data = None
    skill_results = []
    
    # 1. IoT Data
    if state.get("current_station_id"):
        res = iot_skill.run(query="", token=token, station_id=state["current_station_id"])
        iot_data = res.answer
        skill_results.append(res)
    
    # 2. Weather Data
    if state.get("current_location"):
        res = weather_skill.run(query=state["current_location"])
        weather_data = res.answer
        skill_results.append(res)
        
    # 3. PPM Data
    # Fetch PPM data if advice is requested or if the user asks to check projects/tasks/growth stage
    input_lower = state["input"].lower()
    needs_ppm = state["intent"] == "FARMING_ADVICE" or any(kw in input_lower for kw in ["tiến độ", "mùa vụ", "dự án", "project", "task", "công việc"])
    
    if needs_ppm:
        res = progress_skill.run(query="", token=token, status="ALL", project_name=state.get("current_project"))
        ppm_data = res.answer
        skill_results.append(res)
        
    final_res = skill_results[0] if skill_results else None
    if final_res:
        shared["skill_result"] = final_res
        
    # 4. IoT Semantic Translation
    iot_anomalies = None
    if iot_data and "Error" not in iot_data and "no observation" not in iot_data:
        translation_prompt = ChatPromptTemplate.from_messages([
            ("system", "Bạn là chuyên gia Nông nghiệp phân tích dữ liệu IoT. Đọc các chỉ số Cảm biến và dịch thành trạng thái ngữ nghĩa ngắn gọn (Ví dụ: 'Đất nhiễm phèn nặng (pH thấp)', 'Thiếu đạm', 'Nguy cơ nấm bệnh (Độ ẩm cao)'). Nếu các chỉ số nằm trong ngưỡng bình thường, trả về 'Chỉ số môi trường bình thường'."),
            ("user", "Dữ liệu IoT hiện tại:\n{iot_data}")
        ])
        translation_chain = translation_prompt | llm_fast
        iot_anomalies = translation_chain.invoke({"iot_data": iot_data}).content

    print("\n" + "="*50)
    print(f"[DATA GATHERER NODE] IoT Data:\n{iot_data}")
    print(f"[DATA GATHERER NODE] IoT Semantic Translation:\n{iot_anomalies}")
    print(f"[DATA GATHERER NODE] PPM Data:\n{ppm_data}")
    print(f"[DATA GATHERER NODE] Weather Data:\n{weather_data}")
    print("="*50 + "\n")
        
    return {
        "iot_data": iot_data,
        "iot_anomalies": iot_anomalies,
        "ppm_data": ppm_data,
        "weather_data": weather_data
    }


def rag_node(state: AgentState):
    """Queries the agricultural knowledge base."""
    # Build a sophisticated query combining environmental data
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an expert Query Formulator for a Vector Search Engine.
        Your task is to take the user's question and the current Context Data, and formulate 1 to 3 highly precise, concise search queries in Vietnamese.
        
        RULES:
        1. DO NOT include large tables, formatting, or raw dates in your queries.
        2. Identify the CURRENT problem or the IN_PROGRESS task from the Progress Data.
        3. If IoT Semantic Translation reveals an anomaly (e.g., 'Đất nhiễm phèn nặng'), formulate a separate query to address this anomaly during the current task.
        4. Output a LIST of queries that comprehensively cover the necessary knowledge to answer the user.
        
        Example:
        User: "hướng dẫn chăm sóc lúa hôm nay"
        Progress Data: "IN_PROGRESS: Bón lót"
        IoT Semantic Translation: "Đất nhiễm phèn nặng"
        Output: ["Cách bón phân lót cho lúa", "Cách xử lý đất phèn khi bón lót"]
        """),
        ("user", "User Question: {input}\n\nIoT Semantic Translation:\n{iot_anomalies}\n\nProgress Data:\n{ppm_data}")
    ])
    
    chain = prompt | llm_fast.with_structured_output(QueryFormulatorOutput)
    
    try:
        formulated = chain.invoke({
            "input": state["input"],
            "iot_anomalies": state.get("iot_anomalies") or "None",
            "ppm_data": state.get("ppm_data") or "None"
        })
        queries = formulated.search_queries
    except Exception as e:
        print(f"Error in query formulation: {e}")
        queries = [state["input"]]
        
    combined_answers = []
    first_res = None
    
    print("\n" + "="*50)
    for q in queries:
        res = rag_skill.run(query=q)
        if not first_res:
            first_res = res
        print(f"[RAG NODE] Formulated Query: {q}")
        print(f"[RAG NODE] Retrieved Document Snippets:\n{res.answer}\n")
        combined_answers.append(f"--- THÔNG TIN TỪ KHÓA TÌM KIẾM: '{q}' ---\n{res.answer}")
    print("="*50 + "\n")
    
    final_rag_data = "\n\n".join(combined_answers)
    
    import contextvars
    from app.agents.orchestrator import agent_shared_state
    shared = agent_shared_state.get({})
    
    # Prepend the formulated queries to the answer so the user knows what was searched
    queries_str = ", ".join(f"'{q}'" for q in queries)
    if first_res:
        first_res.answer = f"**[Hệ thống đã tìm kiếm tài liệu theo {len(queries)} cụm từ khoá: {queries_str}]**\n\n" + final_rag_data
        shared["skill_result"] = first_res
    
    return {
        "rag_data": final_rag_data
    }


def synthesizer_node(state: AgentState):
    """Formats the final output using the streaming LLM."""
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are FarmMate AI, an expert agricultural consultant.
        
        USER CONTEXT (List of User's Stations):
        {user_context}
        
        CONTEXT DATA FETCHED:
        - IoT Data (Raw): {iot_data}
        - IoT Data (Anomalies Translation): {iot_anomalies}
        - Progress Data: {ppm_data}
        - Weather Data: {weather_data}
        - Technical Manuals (RAG): {rag_data}
        
        RULES:
        1. Always answer in Vietnamese.
        2. If the user asks to list their stations or projects, DO NOT say you don't know! Use the USER CONTEXT to list stations, and Progress Data to list projects.
        3. If the user asks for a station's data but no IoT Data is fetched, kindly ask them to provide the Station ID from the list.
        4. STRICT ANTI-HALLUCINATION FOR MULTI-QUERY: The Technical Manuals (RAG) may contain multiple sections. 
        - Review EACH section. If any section says "does not provide enough information", you MUST explicitly tell the user: "Tài liệu kỹ thuật nội bộ hiện chưa có hướng dẫn chính thức về vấn đề này".
        - If you choose to answer using your own general knowledge for that part, you MUST wrap your advice in a clearly visible warning like this:
        ⚠️ **[Khuyến nghị tham khảo từ kiến thức chung, không nằm trong tài liệu chính xác của dự án]**
        - Do not act like your general knowledge is part of the official manual.
        5. If the Technical Manuals DO provide instructions, you MUST extract and present the specific, actionable advice. DO NOT just say 'I found the document'.
        6. Do NOT hallucinate dosages or fertilizer names if not in the RAG manuals.
        7. When showing Progress Data, MUST use a Markdown Table (Task Name | Project Name | Status | Start Date).
        8. If there are Task Status Statistics, output a valid JSON pie chart block:
        ```chart
        {{
            "type": "pie",
            "data": [ {{"key": "OPEN", "data": 2}}, {{"key": "IN_PROGRESS", "data": 5}} ]
        }}
        ```
        9. For UI Action Links (e.g., suggesting user to check a specific station), use: `[Display Text](#action:Exact_Query_No_Spaces)`
        """),
        ("user", "{input}")
    ])
    
    chain = prompt | llm_stream
    
    res = chain.invoke({
        "input": state["input"],
        "user_context": state.get("user_context", "None"),
        "iot_data": state.get("iot_data") or "None",
        "iot_anomalies": state.get("iot_anomalies") or "None",
        "ppm_data": state.get("ppm_data") or "None",
        "weather_data": state.get("weather_data") or "None",
        "rag_data": state.get("rag_data") or "None"
    })
    
    return {"output": res.content}
