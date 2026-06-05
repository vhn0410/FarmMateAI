import os
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
load_dotenv() 

def get_llm(model: str, temperature: float = 0.0) -> ChatOpenAI:
    """
    Khởi tạo LLM Client dùng chung cho toàn hệ thống.
    Mặc định temperature = 0.0 để câu trả lời mang tính deterministic (chính xác, không sáng tạo thêm).
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("Chưa cấu hình OPENAI_API_KEY trong file .env")

    return ChatOpenAI(
        model=model,
        temperature=temperature,
        api_key=api_key
    )