from fastapi import APIRouter, BackgroundTasks
from schemas.document_dto import (
    SyncResponse,
)  # Tạo schema pydantic để định dạng response
from scripts.cron_ingest_drive import run_ingestion

router = APIRouter()


@router.post("/sync-knowledge", response_model=SyncResponse)
async def sync_knowledge_from_drive(background_tasks: BackgroundTasks):
    """
    Trigger API để đồng bộ dữ liệu nông nghiệp mới nhất từ Google Drive.
    """
    background_tasks.add_task(run_ingestion)
    return SyncResponse(
        status="success", message="Hệ thống đang tiến hành xử lý tài liệu chạy ngầm."
    )
