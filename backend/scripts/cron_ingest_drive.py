import os
import sys

# Add the app root path so the app package can be imported
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.application.documents.use_case import DocumentUseCase

# INFRASTRUCTURE IMPORTS ARE ALLOWED HERE BECAUSE THIS IS AN OUTER LAYER SCRIPT
from app.infrastructure.external.google_drive import GoogleDriveProvider
from app.infrastructure.vector_store.pgvector_provider import PGVectorProvider


def run_ingestion():
    # 1. Initialize the providers
    drive_provider = GoogleDriveProvider()
    vector_store_provider = PGVectorProvider()

    # 2. Inject the providers into the use case
    use_case = DocumentUseCase(
        provider=drive_provider, vector_store_provider=vector_store_provider
    )

    # 3. Run the ingestion flow
    use_case.sync_documents()


if __name__ == "__main__":
    run_ingestion()
