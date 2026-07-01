from fastapi import APIRouter, BackgroundTasks, Depends
from app.schemas.document_dto import (
    SyncResponse,
)
from app.application.documents.use_case import DocumentUseCase
from app.infrastructure.external.google_drive import GoogleDriveProvider
from app.infrastructure.vector_store.pgvector_provider import PGVectorProvider
from app.infrastructure.external.local_file import LocalFileSystemProvider
router = APIRouter()


# Hàm hỗ trợ để FastAPI tự động tiêm dependencies
def get_vector_store_provider():
    """Factory function để tạo PGVectorProvider instance."""
    return PGVectorProvider()


def get_document_use_case(
    vector_store_provider: PGVectorProvider = Depends(
        get_vector_store_provider),
):
    """Factory function để tạo DocumentUseCase với Dependency Injection."""
    from app.infrastructure.external.local_file import LocalFileSystemProvider
    local_provider = LocalFileSystemProvider()
    return DocumentUseCase(
        provider=local_provider, vector_store_provider=vector_store_provider
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
    """Lấy danh sách file PDF từ thư mục nội bộ."""
    local_provider = LocalFileSystemProvider()
    files = local_provider.list_pdf_files()
    return {"status": "success", "data": files}


@router.get("/knowledge-base/files/{file_id}/stream")
def stream_knowledge_base_file(file_id: str):
    """Stream nội dung file PDF trực tiếp từ thư mục cục bộ."""
    from fastapi.responses import FileResponse
    local_provider = LocalFileSystemProvider()
    pdf_path = local_provider.get_pdf_path(file_id)
    if not pdf_path.exists():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename={file_id}"}
    )


@router.post("/knowledge-base/files/upload")
async def upload_knowledge_base_file(
    background_tasks: BackgroundTasks,
    file: __import__('fastapi').UploadFile = __import__('fastapi').File(...),
    use_case: DocumentUseCase = Depends(get_document_use_case)
):
    """Upload một file PDF trực tiếp lên thư mục cục bộ, chạy LlamaParse ngầm, sau đó tự động Vector hóa (Embed)."""
    try:
        from app.infrastructure.external.local_file import LocalFileSystemProvider
        local_provider = LocalFileSystemProvider()
        
        file_bytes = await file.read()
        saved_name = local_provider.save_uploaded_pdf(file.filename, file_bytes)
        
        # Hàm chạy ngầm: Dịch PDF -> MD, sau đó Sync (Embed) ngay lập tức
        def process_and_embed(pdf_name: str, provider: LocalFileSystemProvider, document_use_case: DocumentUseCase):
            # Nếu người dùng đã xóa PDF ngay trước khi bắt đầu LlamaParse
            if not provider.get_pdf_path(pdf_name).exists():
                return
                
            provider.process_pdf_to_md(pdf_name)
            
            # LlamaParse tốn nhiều thời gian. Nếu người dùng xóa PDF trong lúc này,
            # ta phải hủy bỏ việc Sync và dọn dẹp file MD vừa được sinh ra.
            if not provider.get_pdf_path(pdf_name).exists():
                clean_name = pdf_name.replace(".pdf", "")
                provider.delete_file(clean_name)
                return
                
            document_use_case.sync_documents()

        # Đẩy quá trình xử lý vào Background Task
        background_tasks.add_task(process_and_embed, saved_name, local_provider, use_case)
        
        uploaded_file = {
            "id": saved_name,
            "name": saved_name
        }
        return {"status": "success", "data": uploaded_file}
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))
@router.delete("/knowledge-base/files/{file_id}")
async def delete_knowledge_base_file(
    file_id: str,
    use_case: DocumentUseCase = Depends(get_document_use_case)
):
    """Xóa file khỏi bộ nhớ cục bộ và cơ sở dữ liệu Vector."""
    try:
        message = use_case.delete_document(file_id)
        return {"status": "success", "message": message}
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))
