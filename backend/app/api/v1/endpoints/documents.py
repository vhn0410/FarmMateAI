from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
import urllib.parse

from app.schemas.document_dto import SyncResponse
from app.application.documents.use_case import DocumentUseCase
from app.infrastructure.external.google_drive import GoogleDriveProvider
from app.infrastructure.vector_store.pgvector_provider import PGVectorProvider
from app.infrastructure.external.local_file import LocalFileSystemProvider
from app.infrastructure.external.s3_file import S3FileSystemProvider
from app.core.config import settings

router = APIRouter()


# Helper function to let FastAPI inject dependencies automatically
def get_vector_store_provider():
    """Factory function to create a PGVectorProvider instance."""
    return PGVectorProvider()


def get_document_provider():
    """Factory function to create a document provider based on configuration."""
    if settings.storage_provider.lower() == "s3":
        return S3FileSystemProvider()
    return LocalFileSystemProvider()


def get_document_use_case(
    vector_store_provider: PGVectorProvider = Depends(get_vector_store_provider),
    document_provider = Depends(get_document_provider),
):
    """Factory function to create a DocumentUseCase with dependency injection."""
    return DocumentUseCase(
        provider=document_provider, vector_store_provider=vector_store_provider
    )


@router.post("/sync-knowledge", response_model=SyncResponse)
async def sync_knowledge_from_drive():
    """
    Trigger API to sync the latest agricultural data from Google Drive or S3.
    Pushed to Celery Worker to run safely in the background.
    """
    from app.application.documents.tasks import sync_all_documents_task
    sync_all_documents_task.delay()
    
    return SyncResponse(
        status="success", message="The system is processing documents in the background via Celery."
    )


@router.get("/knowledge-base/files")
def get_knowledge_base_files(provider=Depends(get_document_provider)):
    """List PDF files from the local directory or S3."""
    files = provider.list_pdf_files()
    return {"status": "success", "data": files}


@router.get("/knowledge-base/files/{file_id}/stream")
def stream_knowledge_base_file(file_id: str, provider=Depends(get_document_provider)):
    """Stream the contents of a PDF directly from the local filesystem or S3."""
    encoded_filename = urllib.parse.quote(file_id)
    headers = {
        "Content-Disposition": f'inline; filename="document.pdf"; filename*=utf-8\'\'{encoded_filename}'
    }

    if isinstance(provider, S3FileSystemProvider):
        try:
            stream = provider.get_pdf_stream(file_id)
            return StreamingResponse(stream, media_type="application/pdf", headers=headers)
        except Exception:
            raise HTTPException(status_code=404, detail="File not found on S3")
    else:
        pdf_path = provider.get_pdf_path(file_id)
        if not pdf_path.exists():
            raise HTTPException(status_code=404, detail="File not found locally")
        return FileResponse(path=pdf_path, media_type="application/pdf", headers=headers)


@router.post("/knowledge-base/files/upload")
async def upload_knowledge_base_file(
    file: __import__('fastapi').UploadFile = __import__('fastapi').File(...),
    provider = Depends(get_document_provider),
    use_case: DocumentUseCase = Depends(get_document_use_case)
):
    """Upload a PDF file, send a Job to Celery to run LlamaParse in the background, then automatically Embed to Vector DB."""
    try:
        file_bytes = await file.read()
        
        import time
        from pathlib import Path
        
        # Add a timestamp to the filename to ensure it is always unique
        # This prevents S3 overwrites and allows users to process the same file multiple times independently
        original_path = Path(file.filename)
        timestamp = int(time.time())
        unique_filename = f"{original_path.stem}_{timestamp}{original_path.suffix}"
            
        saved_name = provider.save_uploaded_pdf(unique_filename, file_bytes)
        
        # Push the processing task to the Celery Queue
        from app.application.documents.tasks import process_and_embed_task
        process_and_embed_task.delay(saved_name)
        
        uploaded_file = {
            "id": saved_name,
            "name": saved_name,
            "status": "processing"
        }
        return {"status": "success", "data": uploaded_file}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/knowledge-base/files/{file_id}/markdown")
def get_knowledge_base_file_markdown(file_id: str, provider=Depends(get_document_provider)):
    """Retrieve the Markdown content of a PDF file."""
    if isinstance(provider, S3FileSystemProvider):
        content = provider.get_md_content(file_id)
        if content is None:
            raise HTTPException(status_code=404, detail="Markdown file not found on S3")
        return {"status": "success", "data": content}
    else:
        md_path = provider.get_md_path(file_id)
        if not md_path.exists():
            raise HTTPException(status_code=404, detail="Markdown file not found locally")
        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"status": "success", "data": content}


@router.get("/knowledge-base/files/{file_id}/chunks")
def get_knowledge_base_file_chunks(file_id: str, page: int = 1, limit: int = 50):
    """Get the list of chunks in the vector database for a PDF file with pagination."""
    from app.infrastructure.vector_store.pgvector_provider import PGVectorProvider

    vector_provider = PGVectorProvider()
    result = vector_provider.get_chunks_by_file_id(file_id, page=page, limit=limit)
    return {"status": "success", "data": result["data"], "pagination": result["pagination"]}


@router.delete("/knowledge-base/files/{file_id}")
async def delete_knowledge_base_file(
    file_id: str,
    use_case: DocumentUseCase = Depends(get_document_use_case),
    provider = Depends(get_document_provider),
):
    """Delete a file from storage and the vector database."""
    try:
        clean_file_id = file_id.replace(".pdf", "").replace(".md", "")
        if provider.is_locked(clean_file_id):
            raise HTTPException(
                status_code=409, 
                detail="File is currently being processed by a background task and cannot be deleted."
            )
            
        message = use_case.delete_document(file_id)
        return {"status": "success", "message": message}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/knowledge-base/files/{file_id}/graph")
def get_knowledge_base_file_graph(file_id: str):
    """Get the Neo4j knowledge graph data for a PDF file."""
    from app.infrastructure.vector_store.graph_provider import Neo4jGraphProvider

    graph_provider = Neo4jGraphProvider()
    graph_data = graph_provider.get_graph_by_file_id(file_id)
    return {"status": "success", "data": graph_data}
