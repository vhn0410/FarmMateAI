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
from app.agents.mocks.mock_system import MOCK_SYSTEM_DB


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
        """
        CÔNG CỤ TRA CỨU SỔ TAY CHUYÊN GIA NÔNG NGHIỆP.
        !!! CẢNH BÁO ĐỎ CHO THAM SỐ 'query' !!!

        1. TUYỆT ĐỐI KHÔNG BAO GIỜ truyền số liệu thô hoặc kết quả cảm biến vào query (KHÔNG dùng các từ như: "pH 4.5", "N 120", "P 45", "ẩm 40%"). Nếu vi phạm, hệ thống sẽ lỗi.

        2. BẮT BUỘC PHẢI DỊCH số liệu thành TỪ KHÓA CHUYÊN MÔN trước khi tìm kiếm:

           - Nếu pH < 5 -> Phải dịch thành "đất chua", "đất phèn", "cải tạo đất".

           - Nếu N, P, K thấp -> Phải dịch thành "thiếu dinh dưỡng", "bón lót", "bón thúc".

        3. Ví dụ truy vấn ĐÚNG: "Cách bón phân thúc đẻ nhánh cho lúa trên đất chua phèn"

        4. Ví dụ truy vấn SAI: "Cách bón phân lúa pH 4.5 N 120"

        """
        result: SkillResult = rag_skill.run(query)

        # Lấy kho chứa của User hiện tại ra và bỏ kết quả vào
        try:
            state = agent_shared_state.get()
            state["skill_result"] = result
        except LookupError:
            pass  # An toàn bỏ qua nếu test ngoài FastAPI

        return result.answer

    # Cập nhật Tool 2: Lấy IoT theo Trạm
    @tool("Lay_du_lieu_cam_bien_IoT")
    def iot_sensor_tool(station_id: str) -> str:
        """Lấy số liệu cảm biến hiện tại (N,P,K,pH...) của một trạm cụ thể."""
        data = MOCK_SYSTEM_DB["station_data"].get(station_id, {}).get("iot")
        if not data:
            return f"Lỗi: Không tìm thấy dữ liệu cảm biến cho trạm {station_id}."
        return f"Dữ liệu IoT trạm {station_id}: {json.dumps(data)}"

    # Cập nhật Tool 3: Lấy Sinh trưởng theo Trạm
    @tool("Lay_giai_doan_sinh_truong_hien_tai")
    def current_stage_tool(station_id: str) -> str:
        """Lấy thông tin giai đoạn sinh trưởng hiện tại của cây trồng tại trạm."""
        data = MOCK_SYSTEM_DB["station_data"].get(station_id, {}).get("stage")
        if not data:
            return f"Lỗi: Không tìm thấy dữ liệu sinh trưởng cho trạm {station_id}."
        return f"Giai đoạn sinh trưởng trạm {station_id}: {json.dumps(data)}"

    # ==========================================
    # TOOL 4: THỜI TIẾT (Giả lập)
    # ==========================================
    @tool(weather_skill.name)
    def weather_tool(location: str) -> str:
        """Sử dụng công cụ này để lấy thông tin thời tiết (nhiệt độ, mưa, nắng) hiện tại ở một khu vực cụ thể."""
        result: SkillResult = weather_skill.run(
            location
        )  # Truyền location vào làm query
        try:
            state = agent_shared_state.get()
            state["skill_result"] = result
        except LookupError:
            pass
        return result.answer

    # Gộp tất cả tools lại
    tools = [agriculture_tool, iot_sensor_tool, current_stage_tool, weather_tool]

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """Bạn là kỹ sư trưởng tư vấn nông nghiệp AI FarmMate. 

                THÔNG TIN VỀ NGƯỜI DÙNG HIỆN TẠI:
                {user_context}

                KHUNG TƯ DUY XỬ LÝ (BẮT BUỘC TUÂN THỦ):
                
                Bước 1 - PHÂN LOẠI CÂU HỎI & XÁC ĐỊNH BỐI CẢNH:
                - LOẠI 1 (Câu hỏi kiến thức chung): Nếu user hỏi lý thuyết (VD: "Quy trình trồng lúa?", "Phân ure là gì?"), KHÔNG CẦN gọi IoT hay Thời tiết. Hãy bỏ qua bước xác định trạm, gọi trực tiếp công cụ RAG hoặc Quy trình canh tác để trả lời.
                - LOẠI 2 (Câu hỏi về tình trạng vườn thực tế): Nếu user yêu cầu tư vấn hiện tại (VD: "Nay bón phân gì?", "Kiểm tra vườn giúp tôi"):
                   + Hãy xem xét lịch sử trò chuyện và câu hỏi hiện tại. Nếu user CÓ NHIỀU TRẠM nhưng chưa rõ đang nói về trạm nào, hãy DỪNG LẠI và hỏi lịch sự: "Dạ, anh/chị muốn kiểm tra cho trạm nào ạ?".
                   + Nếu user đã nói rõ tên trạm, loại cây, hoặc vị trí khớp với 'THÔNG TIN VỀ NGƯỜI DÙNG', tiến hành lấy 'station_id' và 'location'.

                Bước 2 - THU THẬP DỮ LIỆU (Chỉ dành cho Câu hỏi LOẠI 2): 
                - Dùng 'station_id' gọi Cảm biến IoT và Giai đoạn sinh trưởng.
                - Dùng 'location' gọi Thời tiết.

                Bước 3 - CHUYỂN HÓA & TRUY VẤN RAG:
                - Kết hợp GIAI ĐOẠN SINH TRƯỞNG và TÌNH TRẠNG ĐẤT để dịch thành TỪ KHÓA CHUYÊN MÔN (Không dùng số liệu thô).
                - Gọi công cụ RAG bằng các từ khóa kỹ thuật đó.

                Bước 4 - TỔNG HỢP VÀ TƯ VẤN (KỶ LUẬT THÉP):
                - Nếu RAG có dữ liệu: Hòa trộn kết quả từ IoT, Giai đoạn, Thời tiết và RAG thành đoạn văn tự nhiên. Đưa ra hành động cụ thể BÁM SÁT 100% vào RAG.
                - Nếu RAG báo không đủ thông tin: Tuyệt đối KHÔNG tự suy diễn liều lượng phân bón/thuốc trừ sâu. Chỉ báo cáo tình trạng IoT/Thời tiết và khuyên liên hệ kỹ sư địa phương.""",
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
