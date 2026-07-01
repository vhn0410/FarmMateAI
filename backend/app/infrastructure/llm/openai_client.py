from langchain_openai import ChatOpenAI
from app.domain.interfaces.llm_provider import ILLMProvider

from app.core.config import settings


class OpenAIClient(ILLMProvider):
    """
    Lớp này đóng vai trò là một wrapper để khởi tạo và cung cấp LLM Client của OpenAI.
    Mọi phần khác trong hệ thống khi cần dùng LLM đều sẽ gọi qua lớp này để đảm bảo tính nhất quán.
    """

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        temperature: float = 0.0,
        streaming: bool = False,
    ):
        """Khởi tạo OpenAIClient và đảm bảo API key đã được cấu hình."""
        api_key = settings.openai_api_key
        if not api_key:
            raise ValueError("Chưa cấu hình OPENAI_API_KEY trong file .env")
        self._api_key = api_key
        self._model = model
        self._temperature = temperature
        self._streaming = streaming

    def get_llm(self) -> ChatOpenAI:
        """
        Khởi tạo LLM Client dùng chung cho toàn hệ thống.
        Mặc định temperature = 0.0 để câu trả lời mang tính deterministic (chính xác, không sáng tạo thêm).
        """
        kwargs = {
            "model": self._model,
            "temperature": self._temperature,
            "api_key": self._api_key,
            "streaming": self._streaming,
        }
        
        if settings.openai_api_base:
            kwargs["base_url"] = settings.openai_api_base
            
        return ChatOpenAI(**kwargs)
