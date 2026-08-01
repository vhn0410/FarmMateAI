import os
from typing import Dict, Any, List
from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter

from app.domain.interfaces.document_provider import IDocumentProvider
from app.domain.interfaces.vector_db import IVectorStoreProvider
from app.application.documents.chunking.graph_extractor import GraphExtractor
from app.infrastructure.vector_store.graph_provider import Neo4jGraphProvider


class DocumentUseCase:
    """
    Use case for syncing documents from a provider and saving them to the vector store through PDR.
    """

    def __init__(
        self,
        provider: IDocumentProvider,
        vector_store_provider: IVectorStoreProvider,
        config: Dict[str, Any] = None,
    ):
        self.provider = provider
        self.vector_store_provider = vector_store_provider

        # Initialize the splitter at the use-case layer to create natural parent chunks
        self.markdown_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[
                ("#", "Header_1"),
                ("##", "Header_2"),
                ("###", "Header_3"),
            ],
            strip_headers=False,
        )
        
        # Initialize the graph extractor and provider
        self.graph_extractor = GraphExtractor()
        self.graph_provider = Neo4jGraphProvider()

    def sync_documents(self) -> str:
        """
        Orchestrator function: coordinates the document processing and storage flow.
        """
        raw_documents = self.provider.fetch_new_documents()

        if not raw_documents:
            return "No new documents"

        print(f"📦 Successfully loaded {len(raw_documents)} raw documents.", flush=True)

        natural_parent_docs = []
        processed_file_ids = set()

        for doc in raw_documents:
            # 1. Trích xuất thông tin cơ bản
            source_file = doc.metadata.get("source", "Unknown")
            file_id = doc.metadata.get("file_id") or self._extract_file_id(source_file)
            file_name = self._extract_file_name(doc, source_file)

            processed_file_ids.add(file_id)

            # 2. Split the document into parent chunks based on Markdown structure
            md_split_docs = self.markdown_splitter.split_text(doc.page_content)

            # 3. Attach detailed metadata to each parent chunk
            for md_doc in md_split_docs:
                enriched_doc = self._enrich_metadata(
                    md_doc, source_file, file_id, file_name
                )
                natural_parent_docs.append(enriched_doc)

        print(
            f"✂️ Created {len(natural_parent_docs)} natural parent chunks. Saving to the database...", flush=True
        )

        if not natural_parent_docs:
            print("No natural parent chunks created! Skipping DB insertion.", flush=True)
            return "No documents to sync"

        try:
            # 3.5. Extract and save the knowledge graph to Neo4j
            print(f"🕸️ Extracting a knowledge graph from {len(natural_parent_docs)} parent chunks...", flush=True)
            graph_docs = self.graph_extractor.extract_graph_documents(natural_parent_docs)
            if graph_docs:
                print(f"Saving {len(graph_docs)} graph documents to Neo4j...", flush=True)
                self.graph_provider.add_graph_documents(graph_docs)

            # 4. Delegate child chunking and persistence to the provider (dependency inversion)
            success = self._save_with_pdr_and_mark_processed(
                natural_parent_docs, processed_file_ids
            )
    
            if success:
                print("🎉 Ingestion completed successfully!", flush=True)
                return "Success"
            else:
                # TRIGGER ROLLBACK (SAGA PATTERN)
                print("⚠️ Error while saving to the vector database. Performing full rollback (graph, vector DB, file)...", flush=True)
                for file_id in processed_file_ids:
                    if file_id:
                        try:
                            self.delete_document(file_id)
                        except Exception as rb_e:
                            print(f"❌ Error during rollback for {file_id}: {rb_e}", flush=True)
                return "Error during database save; rollback completed safely"
        except Exception as e:
            # Catch error if save fails, process stops immediately
            print(f"❌ Error during ingestion: {str(e)}. Performing full rollback...", flush=True)
            for file_id in processed_file_ids:
                if file_id:
                    try:
                        self.delete_document(file_id)
                    except Exception as rb_e:
                        print(f"❌ Error during rollback for {file_id}: {rb_e}", flush=True)
            return "Error during database save"

    def _extract_file_id(self, source_file: str) -> str:
        """Extract the file ID for moving the file after processing."""
        if "drive.google.com/file/d/" in source_file:
            return source_file.split("/d/")[1].split("/")[0]
        return source_file

    def _extract_file_name(self, doc: Document, source_file: str) -> str:
        """Handle fallback logic when deriving the file name."""
        file_name = doc.metadata.get("title") or doc.metadata.get("name")
        if not file_name:
            if "drive.google.com" in source_file:
                file_id = self._extract_file_id(source_file)
                return f"Drive_Document_{file_id[:6]}"
            return os.path.basename(source_file)
        return file_name

    def _enrich_metadata(
        self, doc: Document, source_file: str, file_id: str, file_name: str
    ) -> Document:
        """
        Encapsulate the logic for building normalized metadata for a parent document.
        """
        doc.metadata["source"] = source_file
        doc.metadata["file_id"] = file_id
        doc.metadata["file_name"] = file_name
        doc.metadata["allowed_role"] = (
            "admin" if "bao_mat" in file_name.lower() else "public"
        )

        # Build Document Hierarchy an toàn
        h1 = doc.metadata.get("Header_1", "")
        h2 = doc.metadata.get("Header_2", "")
        h3 = doc.metadata.get("Header_3", "")

        hierarchy_parts = [h for h in [h1, h2, h3] if h]
        doc.metadata["document_hierarchy"] = (
            " > ".join(hierarchy_parts) if hierarchy_parts else "Không xác định"
        )

        return doc

    def _save_with_pdr_and_mark_processed(
        self, parent_docs: List[Document], file_ids: set
    ) -> bool:
        """
        Call the PDR from the infrastructure layer to handle full persistence, then mark the files as processed.
        """
        try:
            # Lấy công cụ PDR đã được cấu hình sẵn từ Provider
            pdr_retriever = self.vector_store_provider.get_parent_document_retriever(for_ingestion=True)

            # PDR tự động cắt Child chunks, lưu vào PGVector và lưu Parent vào DocStore (JSONB)
            pdr_retriever.add_documents(parent_docs, ids=None)
            print("✅ Successfully saved to the vector database and doc store.", flush=True)

            # Chỉ mark file as processed KHI VÀ CHỈ KHI lưu DB thành công
            print("🚚 Marking processed files as complete...", flush=True)
            for file_id in file_ids:
                if file_id:
                    # Kiểm tra lại một lần nữa: Nếu PDF gốc bị xóa TRONG QUÁ TRÌNH lưu DB
                    # => Đây là "Tài liệu Zombie", ta phải lập tức Scrub (xóa) nó khỏi DB!
                    if not self.provider.check_pdf_exists(f"{file_id}.pdf"):
                        print(f"⚠️ Detected that file {file_id} was deleted during DB save. Cleaning up zombie chunks!", flush=True)
                        self.delete_document(file_id)
                    else:
                        self.provider.mark_as_processed(file_id)
            return True

        except Exception as e:
            print(f"❌ Critical error while saving to the database: {str(e)}", flush=True)
            return False

    def delete_document(self, file_id: str) -> str:
        """
        Delete an entire document (physical file + vector embeddings).
        """
        # Đảm bảo file_id không chứa đuôi mở rộng
        clean_file_id = file_id.replace(".pdf", "").replace(".md", "")
        
        try:
            # 1. Delete from the graph database first (to avoid orphaned graph nodes if file deletion succeeds but graph cleanup fails)
            if hasattr(self, "graph_provider") and self.graph_provider:
                self.graph_provider.delete_graph_by_file_id(clean_file_id)
                
            # 2. Delete from the vector database (idempotent)
            if hasattr(self.vector_store_provider, "delete_documents_by_file_id"):
                self.vector_store_provider.delete_documents_by_file_id(clean_file_id)
            
            # 3. Delete the physical file last (the frontend relies on it for display)
            if hasattr(self.provider, "delete_file"):
                self.provider.delete_file(clean_file_id)
                
            return "Document deleted successfully"
        except Exception as e:
            print(f"❌ Error deleting document {clean_file_id}: {str(e)}", flush=True)
            raise e
