from pydantic import BaseModel, Field
from typing import List, Optional


class ChatRequest(BaseModel):
    query: str = Field(
        ..., json_schema_extra={"example": "Trồng dừa ở vùng đất mặn cần bón phân gì?"}
    )
    session_id: str = Field(
        default="default_session", description="Dùng để lưu lịch sử chat sau này"
    )


class SourceDocument(BaseModel):
    """Mô tả tài liệu nguồn được trích xuất từ Vector DB"""

    file_name: str = Field(..., json_schema_extra={"example": "Bao_cao_nong_nghiep.md"})
    hierarchy: str = Field(
        ..., json_schema_extra={"example": "1. MỞ ĐẦU > Mô hình tôm"}
    )
    content_snippet: str = Field(
        ...,
        json_schema_extra={
            "example": "Nông nghiệp bền vững là xu hướng phát triển mới trong thời đại công nghệ 4.0."
        },
    )


class TokenUsage(BaseModel):
    """Thống kê số lượng token sử dụng (để tính chi phí)"""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ResponseMetadata(BaseModel):
    """Các dữ liệu siêu dữ liệu dùng để giám sát hệ thống"""

    processing_time_ms: int = Field(
        ...,
        json_schema_extra={"example": 1450},
        description="Thời gian xử lý tính bằng mili-giây",
    )
    tokens_used: Optional[TokenUsage] = None
    agent_actions: List[str] = Field(
        default_factory=list,
        json_schema_extra={"example": ["Tu_van_ky_thuat_nong_nghiep"]},
    )


class ChatData(BaseModel):
    """Khối dữ liệu chính trả về cho Frontend"""

    session_id: str
    answer: str
    sources: List[SourceDocument] = Field(default_factory=list)
    suggested_questions: List[str] = Field(default_factory=list)


class ChatResponse(BaseModel):
    """Cấu trúc bao ngoài cùng của API Response"""

    status: str = Field(default="success", json_schema_extra={"example": "success"})
    data: ChatData
    metadata: Optional[ResponseMetadata] = None
