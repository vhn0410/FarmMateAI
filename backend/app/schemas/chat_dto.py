from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    query: str = Field(..., example="Trồng dừa ở vùng đất mặn cần bón phân gì?")
    session_id: str = Field(default="default_session", description="Dùng để lưu lịch sử chat sau này")

class ChatResponse(BaseModel):
    answer: str
    session_id: str