from abc import ABC, abstractmethod


class ILLMProvider(ABC):
    """
    Interface chuẩn cho mọi dịch vụ cung cấp mô hình ngôn ngữ lớn (LLM) từ bên ngoài.
    Dù sau này dùng OpenAI, Hugging Face, hay Anthropic thì đều phải tuân thủ hợp đồng này.
    """

    @abstractmethod
    def get_llm(self, model: str, temperature: float = 0.0):
        """Khởi tạo và trả về một instance của LLM Client theo model và temperature đã cho."""
        pass
