from unittest.mock import patch
from app.agents.skills.base import SkillResult

# Patch vào đúng đường dẫn của class ChatUseCase trong project của bạn
@patch("app.application.chat.use_case.ChatUseCase._invoke_agent")
def test_chat_api_returns_success_happy_path(mock_invoke_agent, test_client):
    # ==========================================
    # 1. Chuẩn bị (Arrange)
    # ==========================================
    # Tạo một SkillResult giả lập như thể Tool RAG vừa chạy xong
    mock_skill_result = SkillResult(
        answer="Nội dung này LLM không cần đọc vì ta đã mock.",
        skill_name="Tu_van_ky_thuat_nong_nghiep",
        metadata={
            "sources": [
                {"file_name": "Quy_trinh_lua.pdf", "content_snippet": "Bón phân đợt 1"}
            ]
        },
        agent_actions=["Đã tìm thấy tài liệu"],
        tokens_used={"total_tokens": 150}
    )
    
    # Hàm _invoke_agent trong code của bạn trả về một Tuple: (bot_answer, skill_result)
    # Ta ép hàm này trả về câu trả lời cố định:
    mock_invoke_agent.return_value = (
        "Dạ, để trồng lúa ở vùng này, bạn cần bón phân đợt 1 sau 7 ngày.", 
        mock_skill_result
    )

    payload = {
        "query": "Làm sao để bón phân cho lúa?",
        "session_id": "session_nong_dan_001"
    }

    # ==========================================
    # 2. Hành động (Act)
    # ==========================================
    response = test_client.post("/api/v1/chat", json=payload)

    # ==========================================
    # 3. Kiểm tra (Assert)
    # ==========================================
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "success"
    assert data["data"]["session_id"] == "session_nong_dan_001"
    
    # Kiểm tra xem app có bọc câu trả lời giả lập vào đúng cấu trúc JSON không
    assert data["data"]["answer"] == "Dạ, để trồng lúa ở vùng này, bạn cần bón phân đợt 1 sau 7 ngày."
    
    # (Tùy chọn) Nếu UseCase của bạn có gọi LLM để sinh "suggested_questions", 
    # bạn có thể cần mock thêm hàm _generate_suggestions nữa để API chạy mượt 100%.