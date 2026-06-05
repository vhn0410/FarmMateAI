import os
import sys

# Thêm root path để import được thư mục app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.application.documents.use_case import DocumentUseCase

# NƠI NÀY ĐƯỢC PHÉP IMPORT INFRASTRUCTURE VÌ NÓ LÀ OUTER LAYER
from app.infrastructure.external.google_drive import GoogleDriveProvider
from app.infrastructure.vector_store.pgvector_provider import PGVectorProvider


def run_ingestion():
    # 1. Khởi tạo các provider
    drive_provider = GoogleDriveProvider()
    vector_store_provider = PGVectorProvider()

    # 2. "Tiêm" (Inject) các provider vào Use Case
    use_case = DocumentUseCase(
        provider=drive_provider, vector_store_provider=vector_store_provider
    )

    # 3. Chạy
    use_case.sync_documents()


if __name__ == "__main__":
    run_ingestion()
