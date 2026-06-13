import uuid
from sqlalchemy.orm import Session
from passlib.context import CryptContext

# Import cấu hình DB và Model của FarmMateAI
from app.infrastructure.db.session import SessionLocal
from app.infrastructure.db.models import UserModel

# Khởi tạo bộ băm mật khẩu chuẩn Bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def seed_test_user():
    # Mở kết nối Database
    db: Session = SessionLocal()
    try:
        test_username = "nongdan_01"
        test_password = "password123"

        # 1. Kiểm tra xem user đã tồn tại chưa để tránh lỗi trùng lặp
        existing_user = db.query(UserModel).filter(UserModel.username == test_username).first()
        if existing_user:
            print(f"⚠️ User '{test_username}' đã tồn tại trong CSDL.")
            return

        # 2. Băm mật khẩu
        hashed_pw = pwd_context.hash(test_password)

        # 3. Tạo User Model
        new_user = UserModel(
            id=str(uuid.uuid4()),
            username=test_username,
            hashed_password=hashed_pw
        )

        # 4. Lưu vào Database
        db.add(new_user)
        db.commit()
        
        print("✅ Đã nạp dữ liệu thành công!")
        print(f"👉 Username: {test_username}")
        print(f"👉 Password: {test_password}")

    except Exception as e:
        db.rollback()
        print(f"❌ Có lỗi xảy ra: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    print("🚀 Đang chạy script nạp dữ liệu test...")
    seed_test_user()