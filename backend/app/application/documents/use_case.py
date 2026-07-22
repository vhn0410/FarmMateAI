import os
from typing import Dict, Any, List
from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter

from app.domain.interfaces.document_provider import IDocumentProvider
from app.domain.interfaces.vector_db import IVectorStoreProvider
from app.application.documents.chunking.llm_cleaner import LLMDocumentCleaner
from app.application.documents.chunking.graph_extractor import GraphExtractor
from app.application.documents.chunking.graph_extractor import GraphExtractor
from app.infrastructure.vector_store.graph_provider import Neo4jGraphProvider


class DocumentUseCase:
    """
    Use Case cho việc đồng bộ tài liệu từ provider và lưu vào vector store thông qua PDR.
    """

    def __init__(
        self,
        provider: IDocumentProvider,
        vector_store_provider: IVectorStoreProvider,
        config: Dict[str, Any] = None,
    ):
        self.provider = provider
        self.vector_store_provider = vector_store_provider

        # Khởi tạo Splitter duy nhất ở tầng Use Case để tạo Natural Parent Chunks
        self.markdown_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[
                ("#", "Header_1"),
                ("##", "Header_2"),
                ("###", "Header_3"),
            ],
            strip_headers=False,
        )
        
        # Khởi tạo bộ lọc rác LLM
        self.llm_cleaner = LLMDocumentCleaner()
        
        # Khởi tạo Graph Extractor và Provider
        self.graph_extractor = GraphExtractor()
        self.graph_provider = Neo4jGraphProvider()

    def sync_documents(self) -> str:
        """
        Hàm Orchestrator: Điều phối luồng xử lý và lưu trữ tài liệu.
        """
        raw_documents = self.provider.fetch_new_documents()

        if not raw_documents:
            return "Không có tài liệu mới"

        print(f"📦 Đã load thành công {len(raw_documents)} tài liệu thô.", flush=True)

        natural_parent_docs = []
        processed_file_ids = set()

        for doc in raw_documents:
            # 1. Trích xuất thông tin cơ bản
            source_file = doc.metadata.get("source", "Unknown")
            file_id = doc.metadata.get("file_id") or self._extract_file_id(source_file)
            file_name = self._extract_file_name(doc, source_file)

            processed_file_ids.add(file_id)

            # 2. Cắt tài liệu thành các Parent Chunks dựa trên Markdown
            md_split_docs = self.markdown_splitter.split_text(doc.page_content)

            # 2.5 Dọn rác bằng LLM cho các chunks vừa sinh ra
            print(f"🧹 Đang gọi LLM (gpt-4o-mini) dọn rác cho {len(md_split_docs)} Parent Chunks...", flush=True)
            clean_md_docs = self.llm_cleaner.clean_documents(md_split_docs)

            # 3. Gắn metadata chi tiết cho từng Parent Chunk
            for md_doc in clean_md_docs:
                enriched_doc = self._enrich_metadata(
                    md_doc, source_file, file_id, file_name
                )
                natural_parent_docs.append(enriched_doc)

        print(
            f"✂️ Đã tạo {len(natural_parent_docs)} Parent Chunks tự nhiên. Tiến hành lưu database...", flush=True
        )

        try:
            # 3.5. Trích xuất và lưu Knowledge Graph vào Neo4j
            print(f"🕸️ Đang trích xuất Knowledge Graph từ {len(natural_parent_docs)} Parent Chunks...", flush=True)
            graph_docs = self.graph_extractor.extract_graph_documents(natural_parent_docs)
            if graph_docs:
                print(f"Lưu {len(graph_docs)} Graph Documents vào Neo4j...", flush=True)
                self.graph_provider.add_graph_documents(graph_docs)
    
            # 4. Giao phó việc cắt Child & lưu trữ cho Provider (Dependency Inversion)
            success = self._save_with_pdr_and_mark_processed(
                natural_parent_docs, processed_file_ids
            )
    
            if success:
                print("🎉 Quá trình Ingestion hoàn tất 100%!", flush=True)
                return "Thành công"
            else:
                # KÍCH HOẠT ROLLBACK (SAGA PATTERN)
                print("⚠️ Lỗi khi lưu Vector DB. Tiến hành Rollback toàn diện (Graph, Vector DB, File)...", flush=True)
                for file_id in processed_file_ids:
                    if file_id:
                        try:
                            self.delete_document(file_id)
                        except Exception as rb_e:
                            print(f"❌ Lỗi khi rollback cho {file_id}: {rb_e}", flush=True)
                return "Lỗi trong quá trình lưu Database, đã Rollback an toàn"
        except Exception as e:
            # Bắt lỗi nếu quá trình lưu thất bại, tiến trình dừng lại luôn
            print(f"❌ Lỗi trong quá trình Ingestion: {str(e)}. Đang Rollback toàn diện...", flush=True)
            for file_id in processed_file_ids:
                if file_id:
                    try:
                        self.delete_document(file_id)
                    except Exception as rb_e:
                        print(f"❌ Lỗi khi rollback cho {file_id}: {rb_e}", flush=True)
            return "Lỗi trong quá trình lưu Database"

    def _extract_file_id(self, source_file: str) -> str:
        """Trích xuất File ID phục vụ việc di chuyển file sau khi xong."""
        if "drive.google.com/file/d/" in source_file:
            return source_file.split("/d/")[1].split("/")[0]
        return source_file

    def _extract_file_name(self, doc: Document, source_file: str) -> str:
        """Xử lý fallback logic khi lấy tên file."""
        file_name = doc.metadata.get("title") or doc.metadata.get("name")
        if not file_name:
            if "drive.google.com" in source_file:
                file_id = self._extract_file_id(source_file)
                return f"Tài_liệu_Drive_{file_id[:6]}"
            return os.path.basename(source_file)
        return file_name

    def _enrich_metadata(
        self, doc: Document, source_file: str, file_id: str, file_name: str
    ) -> Document:
        """
        Đóng gói toàn bộ logic build metadata chuẩn hóa cho Parent Document.
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
        Gọi PDR từ tầng Infrastructure để xử lý lưu trữ toàn diện, sau đó đánh dấu file.
        """
        try:
            # Lấy công cụ PDR đã được cấu hình sẵn từ Provider
            pdr_retriever = self.vector_store_provider.get_parent_document_retriever(for_ingestion=True)

            # PDR tự động cắt Child chunks, lưu vào PGVector và lưu Parent vào DocStore (JSONB)
            pdr_retriever.add_documents(parent_docs, ids=None)
            print("✅ Đã lưu thành công vào Vector Database và DocStore.", flush=True)

            # Chỉ mark file as processed KHI VÀ CHỈ KHI lưu DB thành công
            print("🚚 Đang đánh dấu hoàn tất các file đã xử lý...", flush=True)
            for file_id in file_ids:
                if file_id:
                    # Kiểm tra lại một lần nữa: Nếu PDF gốc bị xóa TRONG QUÁ TRÌNH lưu DB
                    # => Đây là "Tài liệu Zombie", ta phải lập tức Scrub (xóa) nó khỏi DB!
                    if not self.provider.check_pdf_exists(f"{file_id}.pdf"):
                        print(f"⚠️ Phát hiện file {file_id} bị xóa ngang lúc lưu DB. Tiến hành dọn dẹp Zombie Chunks!", flush=True)
                        self.vector_store_provider.delete_documents_by_file_id(file_id)
                        # Dọn luôn file MD
                        self.provider.delete_file(file_id)
                    else:
                        self.provider.mark_as_processed(file_id)
            return True

        except Exception as e:
            print(f"❌ Lỗi nghiêm trọng khi lưu DB: {str(e)}", flush=True)
            return False

    def delete_document(self, file_id: str) -> str:
        """
        Xóa toàn bộ tài liệu (File vật lý + Vector Embeddings).
        """
        # Đảm bảo file_id không chứa đuôi mở rộng
        clean_file_id = file_id.replace(".pdf", "").replace(".md", "")
        
        try:
            # 1. Xóa trong Graph DB trước tiên (Bảo đảm Graph không bị bỏ rơi nếu File xóa thành công mà Graph thất bại)
            if hasattr(self, "graph_provider") and self.graph_provider:
                self.graph_provider.delete_graph_by_file_id(clean_file_id)
                
            # 2. Xóa trong CSDL Vector (Idempotent)
            if hasattr(self.vector_store_provider, "delete_documents_by_file_id"):
                self.vector_store_provider.delete_documents_by_file_id(clean_file_id)
            
            # 3. Xóa File vật lý (Hành động cuối cùng, vì Frontend dựa vào file này để hiển thị)
            if hasattr(self.provider, "delete_file"):
                self.provider.delete_file(clean_file_id)
                
            return "Xóa tài liệu thành công"
        except Exception as e:
            print(f"❌ Lỗi khi xóa tài liệu {clean_file_id}: {str(e)}", flush=True)
            raise e
