from fastapi import APIRouter, BackgroundTasks, Depends
from app.schemas.document_dto import (
    SyncResponse,
)  # Tạo schema pydantic để định dạng response
from app.application.documents.use_case import DocumentUseCase
from app.infrastructure.external.google_drive import GoogleDriveProvider

router = APIRouter()


# Hàm hỗ trợ lắp ráp để FastAPI tự động tiêm
def get_document_use_case():
    drive_provider = GoogleDriveProvider()
    return DocumentUseCase(provider=drive_provider)


@router.post("/sync-knowledge", response_model=SyncResponse)
async def sync_knowledge_from_drive(
    background_tasks: BackgroundTasks,
    use_case: DocumentUseCase = Depends(get_document_use_case),
):
    """
    Trigger API để đồng bộ dữ liệu nông nghiệp mới nhất từ Google Drive.
    """
    background_tasks.add_task(use_case.sync_documents)
    return SyncResponse(
        status="success", message="Hệ thống đang tiến hành xử lý tài liệu chạy ngầm."
    )
