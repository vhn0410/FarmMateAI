from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings

# 1. Khởi tạo Engine kết nối Database
# pool_pre_ping=True giúp tự động kiểm tra và tái kết nối nếu DB bị ngắt giữa chừng
engine = create_engine(
    settings.postgres_connection_string, 
    pool_pre_ping=True
)

# 2. Tạo Factory quản lý các phiên làm việc (Session)
SessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine
)

def get_db() -> Generator[Session, None, None]:
    """
    Dependency Generator cấp phát DB Session cho từng Request.
    Được tối ưu để sử dụng chung với FastAPI Depends.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        # Luôn đảm bảo đóng kết nối để giải phóng tài nguyên cho hệ thống
        db.close()