from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.api.v1.router import api_router
from fastapi.middleware.cors import CORSMiddleware
from app.infrastructure.db.init_db import initialize_database

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Khởi tạo DB tự động (chỉ tạo bảng nếu chưa có, không xóa dữ liệu)
    initialize_database()
    yield
    # Cleanup (nếu cần giải phóng tài nguyên)

# Khởi tạo ứng dụng FastAPI
app = FastAPI(
    title="FarmMate AI API",
    description="Hệ thống Backend AI tư vấn nông nghiệp",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Cho phép Frontend từ mọi port gọi tới
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gắn toàn bộ router v1 vào ứng dụng chính
# Tiền tố ở lớp ngoài cùng là /api/v1
app.include_router(api_router, prefix="/api/v1")


# Một API nhỏ để kiểm tra server có đang chạy hay không
@app.get("/")
def health_check():
    return {"status": "ok", "message": "Backend FarmMate AI is running!"}
