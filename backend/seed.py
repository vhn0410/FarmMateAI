import uuid
from sqlalchemy.orm import Session
from passlib.context import CryptContext

# Import cấu hình DB và Model của FarmMateAI
from app.infrastructure.db.session import SessionLocal
from app.infrastructure.db.models import UserModel

# Khởi tạo bộ băm mật khẩu chuẩn Bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def seed_test_user():
    # Open the database connection
    db: Session = SessionLocal()
    try:
        test_username = "nongdan_01"
        test_password = "password123"

        # 1. Check whether the user already exists to avoid duplicates
        existing_user = db.query(UserModel).filter(UserModel.username == test_username).first()
        if existing_user:
            print(f"⚠️ User '{test_username}' already exists in the database.")
            return

        # 2. Hash the password
        hashed_pw = pwd_context.hash(test_password)

        # 3. Create the user model
        new_user = UserModel(
            id=str(uuid.uuid4()),
            username=test_username,
            hashed_password=hashed_pw
        )

        # 4. Save to the database
        db.add(new_user)
        db.commit()
        
        print("✅ Seed data loaded successfully!")
        print(f"👉 Username: {test_username}")
        print(f"👉 Password: {test_password}")

    except Exception as e:
        db.rollback()
        print(f"❌ An error occurred: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    print("🚀 Running the test data seeding script...")
    seed_test_user()