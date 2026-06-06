# app/agents/skills/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SkillResult:
    """
    Kết quả chung của mọi Skill. Mỗi skill có thể define riêng cấu trúc của metadata
    dựa trên nhu cầu của nó.

    Ví dụ:
    - RAG Skill: metadata = {"sources": [...], "retrieved_docs": [...]}
    - Weather Skill (future): metadata = {"location": "...", "temperature": ..., "forecast": [...]}
    - Sensor Skill (future): metadata = {"device_id": "...", "readings": [...]}
    """

    answer: str  # Câu trả lời chính (bắt buộc)
    skill_name: str  # Tên skill (bắt buộc) - để use_case biết xử lý metadata thế nào
    metadata: Dict[str, Any] = field(
        default_factory=dict
    )  # Metadata linh hoạt từng skill
    tokens_used: Optional[Dict[str, int]] = None  # {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    agent_actions: List[str] = field(
        default_factory=list
    )  # ["Retrieved N documents", "Generated answer", ...]


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
    def run(self, query: str, **kwargs) -> SkillResult:
        """
        Hàm thực thi chính đồng bộ (Synchronous).
        Mọi class kế thừa BẮT BUỘC phải viết đè (override) hàm này.

        :param query: Đầu vào mà LLM truyền cho công cụ (thường là câu hỏi của user).
        :param kwargs: Các tham số linh hoạt khác.
        :return: SkillResult chứa answer, metadata, tokens_used, agent_actions.
        """
        pass

    async def arun(self, query: str, **kwargs) -> SkillResult:
        """
        Hàm thực thi bất đồng bộ (Asynchronous).
        (Không bắt buộc phải override nếu skill chỉ chạy đồng bộ).
        Rất hữu ích khi FastAPI cần gọi các Skill gọi API bên ngoài (IoT, Weather) để không chặn luồng (non-blocking).
        """
        # Nếu class con không định nghĩa hàm arun, mặc định sẽ ném lỗi này.
        raise NotImplementedError(
            f"Skill '{self.name}' chưa hỗ trợ thực thi bất đồng bộ (async)."
        )
