import traceback
from app.infrastructure.celery.celery_app import celery_app
from app.api.v1.endpoints.documents import (
    get_document_provider,
    get_vector_store_provider,
    get_document_use_case,
)

@celery_app.task(bind=True, max_retries=3)
def process_and_embed_task(self, pdf_name: str):
    """
    Background Task to parse a PDF file and save it to the Vector Database.
    If it fails due to a temporary error, it can automatically retry.
    """
    try:
        # In a Celery Worker, FastAPI Depends does not work automatically.
        # We must manually initialize the Providers and UseCase.
        provider = get_document_provider()
        vector_provider = get_vector_store_provider()
        use_case = get_document_use_case(vector_store_provider=vector_provider, document_provider=provider)
        
        file_id = pdf_name.replace(".pdf", "")
        provider.create_lock(file_id)

        # Step 1: Translate PDF -> MD (Call AI Vision)
        print(f"Start processing PDF: {pdf_name}", flush=True)
        provider.process_pdf_to_md(pdf_name)
        
        # Step 2: Read MD file, Chunking, and save to Vector Store + Graph
        print(f"Start syncing Vector DB for file: {pdf_name}", flush=True)
        sync_result = use_case.sync_documents()
        
        if sync_result != "Success":
            raise Exception(f"Failed to sync vector DB: {sync_result}")
        
        print(f"Successfully processed all parts for {pdf_name}!", flush=True)
        return {"status": "success", "file": pdf_name}
        
    except Exception as exc:
        print(f"Error processing document {pdf_name}: {exc}", flush=True)
        traceback.print_exc()
        
        if self.request.retries >= self.max_retries:
            print(f"Max retries reached for {pdf_name}. Rolling back completely!", flush=True)
            use_case.delete_document(pdf_name)
            raise exc
            
        # Retry the task if an error occurs (retry after 60 seconds)
        raise self.retry(exc=exc, countdown=60)
    finally:
        if 'provider' in locals() and 'file_id' in locals():
            provider.remove_lock(file_id)

@celery_app.task(bind=True, max_retries=3)
def sync_all_documents_task(self):
    """
    Background Task to scan all new MD files and sync them.
    """
    try:
        provider = get_document_provider()
        vector_provider = get_vector_store_provider()
        use_case = get_document_use_case(vector_store_provider=vector_provider, document_provider=provider)
        
        print("Start syncing all documents...", flush=True)
        message = use_case.sync_documents()
        return {"status": "success", "message": message}
    except Exception as exc:
        print(f"Error syncing all documents: {exc}", flush=True)
        traceback.print_exc()
        raise self.retry(exc=exc, countdown=60)
