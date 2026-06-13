from unittest.mock import patch, Mock
from app.agents.skills.weather.tool import WeatherSkill


# Dùng @patch để "trói" hàm requests.get lại, không cho nó gọi ra Internet thực tế
@patch("app.agents.skills.weather.tool.requests.get")
def test_weather_skill_returns_success_happy_path(mock_get):
    # ==========================================
    # 1. Chuẩn bị (Arrange)
    # ==========================================
    skill = WeatherSkill()

    # Tạo một "Response Giả" y hệt như những gì OpenWeatherMap trả về khi thành công
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "main": {"temp": 32.5, "humidity": 70},
        "weather": [{"description": "nắng đẹp"}],
        "name": "Hồ Chí Minh",
    }

    # Nhét response giả này vào tay diễn viên đóng thế (mock_get)
    mock_get.return_value = mock_response

    # ==========================================
    # 2. Hành động (Act)
    # ==========================================
    # Gọi hàm run với tên thành phố bất kỳ
    result = skill.run("Hồ Chí Minh")

    # ==========================================
    # 3. Kiểm tra (Assert)
    # ==========================================
    # Đảm bảo requests.get đã được gọi đúng 1 lần (Agent không gọi lặp)
    mock_get.assert_called_once()

    # Đảm bảo Tool bóc tách đúng nhiệt độ và độ ẩm nhét vào câu trả lời
    assert "32.5" in result.answer
    assert "nắng đẹp" in result.answer
    assert "Hồ Chí Minh" in result.answer

    # Kiểm tra metadata lưu trữ đúng
    assert result.metadata["temperature"] == 32.5
