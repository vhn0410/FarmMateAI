from fastapi import APIRouter, BackgroundTasks, Depends
from app.schemas.document_dto import (
    SyncResponse,
)
from app.application.documents.use_case import DocumentUseCase
from app.infrastructure.external.google_drive import GoogleDriveProvider
from app.infrastructure.vector_store.pgvector_provider import PGVectorProvider

router = APIRouter()


# Hàm hỗ trợ để FastAPI tự động tiêm dependencies
def get_vector_store_provider():
    """Factory function để tạo PGVectorProvider instance."""
    return PGVectorProvider()


def get_document_use_case(
    vector_store_provider: PGVectorProvider = Depends(get_vector_store_provider),
):
    """Factory function để tạo DocumentUseCase với Dependency Injection."""
    drive_provider = GoogleDriveProvider()
    return DocumentUseCase(
        provider=drive_provider, vector_store_provider=vector_store_provider
    )


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


@router.get("/knowledge-base/files")
def get_knowledge_base_files():
    """Lấy danh sách file PDF từ thư mục Knowledge Base cố định."""
    folder_id = "1MvldLo1vOeDxgOPiSlk82679n1U0zWkD"
    drive_provider = GoogleDriveProvider()
    files = drive_provider.list_pdf_files(folder_id)
    return {"status": "success", "data": files}


@router.get("/knowledge-base/files/{file_id}/stream")
def stream_knowledge_base_file(file_id: str):
    """Stream nội dung file PDF trực tiếp từ Google Drive."""
    from fastapi.responses import StreamingResponse
    drive_provider = GoogleDriveProvider()
    return StreamingResponse(
        drive_provider.stream_file_generator(file_id),
        media_type="application/pdf"
    )

@router.post("/knowledge-base/files/upload")
async def upload_knowledge_base_file(file: __import__('fastapi').UploadFile = __import__('fastapi').File(...)):
    """Upload một file PDF trực tiếp lên thư mục Knowledge Base."""
    try:
        folder_id = "1MvldLo1vOeDxgOPiSlk82679n1U0zWkD"
        drive_provider = GoogleDriveProvider()
        
        file_bytes = await file.read()
        uploaded_file = drive_provider.upload_file(
            file_name=file.filename,
            file_bytes=file_bytes,
            mime_type=file.content_type,
            folder_id=folder_id
        )
        return {"status": "success", "data": uploaded_file}
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))
