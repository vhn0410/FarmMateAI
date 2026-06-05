import os
import sys
# Thêm root path để import được thư mục app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.application.documents.use_case import DocumentUseCase
# NƠI NÀY ĐƯỢC PHÉP IMPORT INFRASTRUCTURE VÌ NÓ LÀ OUTER LAYER
from app.infrastructure.external.google_drive import GoogleDriveProvider


def run_ingestion():
    # 1. Khởi tạo cục máy thực tế
    drive_provider = GoogleDriveProvider()

    # 2. "Tiêm" (Inject) cục máy vào Use Case
    use_case = DocumentUseCase(provider=drive_provider)

    # 3. Chạy
    use_case.sync_documents()


if __name__ == "__main__":
    run_ingestion()
