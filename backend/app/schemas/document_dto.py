from pydantic import BaseModel, Field


class SyncResponse(BaseModel):
    """
    Schema định nghĩa cấu trúc dữ liệu trả về khi gọi API đồng bộ tài liệu.
    """

    status: str = Field(
        ...,
        json_schema_extra={"example": "success"},
        description="Trạng thái của tiến trình (ví dụ: success, pending, error)",
    )
    message: str = Field(
        ...,
        json_schema_extra={
            "example": "Hệ thống đang tiến hành xử lý tài liệu chạy ngầm."
        },
        description="Thông báo chi tiết gửi đến người dùng/frontend",
    )
