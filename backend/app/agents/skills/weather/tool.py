import requests

from app.agents.skills.base import BaseSkill, SkillResult
from app.core.config import settings


class WeatherSkill(BaseSkill):
    name = "Lay_du_lieu_thoi_tiet"
    description = (
        "Sử dụng công cụ này để lấy thông tin thời tiết (nhiệt độ, độ ẩm, tình trạng mây/mưa) "
        "hiện tại ở một tỉnh, thành phố hoặc khu vực cụ thể."
    )

    def __init__(self):
        """Khởi tạo Tool Thời tiết."""
        # Lấy API key từ biến môi trường
        self.api_key = settings.openweathermap_api_key
        self.base_url = settings.openweathermap_base_url

    def run(self, query: str, **kwargs) -> SkillResult:
        """
        Thực thi lấy dữ liệu thời tiết.
        Biến 'query' ở đây chính là tên địa điểm (location) do LLM truyền vào.
        """
        location = query.strip()
        agent_actions = [f"Bắt đầu lấy dữ liệu thời tiết cho khu vực: '{location}'"]

        # Kiểm tra xem đã cấu hình API Key chưa
        if not self.api_key:
            error_msg = "Hệ thống chưa được cấu hình OPENWEATHERMAP_API_KEY."
            agent_actions.append("Lỗi: Thiếu API Key.")
            return SkillResult(
                answer=error_msg,
                skill_name=self.name,
                metadata={},
                agent_actions=agent_actions,
            )

        try:
            # Tham số gửi lên OpenWeatherMap
            params = {
                "q": location,
                "appid": self.api_key,
                "units": "metric",  # Lấy nhiệt độ theo độ C (Celsius)
                "lang": "vi",  # Trả về mô tả bằng Tiếng Việt
            }

            agent_actions.append("Đang gửi HTTP GET request tới OpenWeatherMap...")
            response = requests.get(self.base_url, params=params, timeout=10)

            # Xử lý kết quả trả về
            if response.status_code == 200:
                data = response.json()

                # Bóc tách các thông số quan trọng
                temp = data["main"]["temp"]
                humidity = data["main"]["humidity"]
                description = data["weather"][0]["description"]
                city_name = data["name"]

                # Tạo câu trả lời cho LLM đọc
                answer = (
                    f"Dữ liệu thời tiết hiện tại ở {city_name}: "
                    f"Trời {description}, nhiệt độ {temp}°C, độ ẩm {humidity}%."
                )
                agent_actions.append(f"Thành công: {answer}")

                return SkillResult(
                    answer=answer,
                    skill_name=self.name,
                    metadata={
                        "location_requested": location,
                        "location_found": city_name,
                        "temperature": temp,
                        "humidity": humidity,
                        "description": description,
                    },
                    agent_actions=agent_actions,
                )

            elif response.status_code == 404:
                # Trường hợp LLM đưa ra tên địa danh không tồn tại
                answer = f"Không tìm thấy trạm dữ liệu thời tiết nào cho khu vực '{location}'."
                agent_actions.append(f"Lỗi 404: Không tìm thấy địa danh '{location}'.")
                return SkillResult(
                    answer=answer,
                    skill_name=self.name,
                    metadata={},
                    agent_actions=agent_actions,
                )

            else:
                answer = f"Lỗi gọi API thời tiết. Mã lỗi: {response.status_code}."
                agent_actions.append(f"Lỗi API: {response.text}")
                return SkillResult(
                    answer=answer,
                    skill_name=self.name,
                    metadata={},
                    agent_actions=agent_actions,
                )

        except Exception as e:
            error_msg = f"Lỗi hệ thống khi tra cứu thời tiết: {str(e)}"
            agent_actions.append(error_msg)
            return SkillResult(
                answer=error_msg,
                skill_name=self.name,
                metadata={},
                agent_actions=agent_actions,
            )
