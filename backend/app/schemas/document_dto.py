from pydantic import BaseModel, Field


class SyncResponse(BaseModel):
    """
    Schema định nghĩa cấu trúc dữ liệu trả về khi gọi API đồng bộ tài liệu.
    """

    status: str = Field(
        ...,
        example="success",
        description="Trạng thái của tiến trình (ví dụ: success, pending, error)",
    )
    message: str = Field(
        ...,
        example="Hệ thống đang tiến hành xử lý tài liệu chạy ngầm.",
        description="Thông báo chi tiết gửi đến người dùng/frontend",
    )
