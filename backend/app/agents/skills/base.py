# app/agents/skills/base.py
from abc import ABC, abstractmethod
from typing import Any, Optional

class BaseSkill(ABC):
    """
    Interface (Abstract Base Class) chuẩn cho mọi kỹ năng (Skill/Tool) của hệ thống AI.
    Mọi Skill mới tạo ra đều phải kế thừa class này.
    """
    
    # 1. Tên của công cụ (Bắt buộc)
    # Tên này không được chứa khoảng trắng. Agent (LLM) sẽ dựa vào tên này để gọi.
    name: str 
    
    # 2. Mô tả công cụ (Cực kỳ quan trọng)
    # Đây là "Prompt" để LLM tự quyết định xem khi nào thì nên xách công cụ này ra xài.
    description: str 

    @abstractmethod
    def run(self, query: str, **kwargs) -> str:
        """
        Hàm thực thi chính đồng bộ (Synchronous).
        Mọi class kế thừa BẮT BUỘC phải viết đè (override) hàm này.
        
        :param query: Đầu vào mà LLM truyền cho công cụ (thường là câu hỏi của user).
        :param kwargs: Các tham số linh hoạt khác.
        :return: Kết quả xử lý dưới dạng chuỗi (String) để LLM đọc và tổng hợp.
        """
        pass

    async def arun(self, query: str, **kwargs) -> str:
        """
        Hàm thực thi bất đồng bộ (Asynchronous).
        (Không bắt buộc phải override nếu skill chỉ chạy đồng bộ).
        Rất hữu ích khi FastAPI cần gọi các Skill gọi API bên ngoài (IoT, Weather) để không chặn luồng (non-blocking).
        """
        # Nếu class con không định nghĩa hàm arun, mặc định sẽ ném lỗi này.
        raise NotImplementedError(f"Skill '{self.name}' chưa hỗ trợ thực thi bất đồng bộ (async).")