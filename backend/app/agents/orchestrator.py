import contextvars
import json
from langchain_classic.agents.openai_tools.base import create_openai_tools_agent
from langchain_classic.agents.agent import AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool

from app.agents.skills.rag_agriculture.tool import AgricultureRAGSkill
from app.agents.skills.weather.tool import WeatherSkill
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
    weather_skill = WeatherSkill()

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

    # ==========================================
    # TOOL 2: CẢM BIẾN IOT (Giả lập)
    # ==========================================
    @tool("Lay_du_lieu_cam_bien_IoT")
    def iot_sensor_tool(farm_id: str = "mac_dinh") -> str:
        """Sử dụng công cụ này ĐỂ ĐỌC SỐ LIỆU THỰC TẾ từ trạm cảm biến tại vườn (N, P, K, pH, nhiệt độ, độ ẩm đất, EC)."""
        # Trả về JSON string giả lập
        mock_data = {
            "N": "120 mg/kg (Thấp)",
            "P": "45 mg/kg (Trung bình)",
            "K": "180 mg/kg (Khá)",
            "pH": 4.5,
            "nhiet_do_dat": 29.5,
            "do_am_dat": 40,
            "EC": 3.2,
        }
        return f"Dữ liệu cảm biến hiện tại: {json.dumps(mock_data, ensure_ascii=False)}"

    # ==========================================
    # TOOL 3: QUY TRÌNH CANH TÁC (Giả lập)
    # ==========================================
    @tool("Tra_cuu_quy_trinh_canh_tac")
    def farming_process_tool(crop_name: str) -> str:
        """Sử dụng công cụ này để lấy các bước/giai đoạn trong quy trình canh tác của một loại cây trồng cụ thể."""
        crop_name = crop_name.lower()
        if "lúa" in crop_name:
            return "Quy trình lúa: 1. Làm đất/Sạ -> 2. Bón phân đợt 1 (7-10 ngày) -> 3. Đẻ nhánh -> 4. Làm đòng -> 5. Trổ bông."
        elif "xoài" in crop_name:
            return "Quy trình xoài: 1. Phục hồi sau thu hoạch -> 2. Xử lý ra hoa -> 3. Chăm sóc trái non -> 4. Bao trái."
        else:
            return f"Quy trình chung cho {crop_name}: 1. Chuẩn bị đất -> 2. Gieo/Trồng -> 3. Bón phân -> 4. Thu hoạch."

    # ==========================================
    # TOOL 4: THỜI TIẾT (Giả lập)
    # ==========================================
    @tool(weather_skill.name)
    def weather_tool(location: str) -> str:
        """Sử dụng công cụ này để lấy thông tin thời tiết (nhiệt độ, mưa, nắng) hiện tại ở một khu vực cụ thể."""
        result: SkillResult = weather_skill.run(location) # Truyền location vào làm query
        try:
            state = agent_shared_state.get()
            state["skill_result"] = result
        except LookupError:
            pass
        return result.answer

    # Gộp tất cả tools lại
    tools = [agriculture_tool, iot_sensor_tool, farming_process_tool, weather_tool]

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """Bạn là kỹ sư tư vấn nông nghiệp AI FarmMate. Bạn có quyền truy cập vào 4 hệ thống: 
                1. Dữ liệu cảm biến IoT thực tế tại vườn.
                2. Dữ liệu thời tiết trực tuyến.
                3. Quy trình canh tác chuẩn.
                4. Hệ thống tài liệu chuyên gia (RAG).
                
                LƯU Ý QUAN TRỌNG: 
                - Hãy chủ động suy luận. Nếu người dùng hỏi tình trạng cây, hãy tự động gọi công cụ Thời tiết và Cảm biến để kiểm tra số liệu, sau đó kết hợp với RAG và Quy trình canh tác để đưa ra chẩn đoán và giải pháp. Trả lời súc tích và có tính chuyên môn cao.
                - Khi gọi công cụ thời tiết, nếu địa danh là một Huyện/Xã nhỏ (như Cù Lao Dung) mà công cụ báo lỗi không tìm thấy, hãy tự động suy luận xem Huyện/Xã đó thuộc Tỉnh/Thành phố nào (VD: Sóc Trăng) và gọi lại công cụ thời tiết bằng tên Tỉnh/Thành phố đó để lấy dữ liệu chung.""",
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
