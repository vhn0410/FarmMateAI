from typing import List, Any
from langchain_core.documents import Document
from app.domain.interfaces.vector_db import IVectorStoreProvider

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_postgres import PGVector
from app.core.config import settings
from app.infrastructure.vector_store.hybrid_retriever import PostgresHybridRetriever, HybridParentDocumentRetriever
from sqlalchemy import create_engine, text
from langchain_classic.retrievers.parent_document_retriever import (
    ParentDocumentRetriever,
)
from app.infrastructure.vector_store.pg_docstore import PostgresDocStore
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Đọc từ biến môi trường (cấu hình trong file .env)
DB_CONNECTION = settings.postgres_connection_string
COLLECTION_NAME = settings.collection_name


class PGVectorProvider(IVectorStoreProvider):
    """
    Concrete implementation của IVectorStoreProvider cho PostgreSQL + pgvector.

    Mục đích:
    - Wrap PGVector object
    - Implement interface chuẩn IVectorStoreProvider
    - Cho phép dependency injection vào các Skill và Use Case
    """

    def __init__(self):
        """Khởi tạo PGVector instance thông qua factory function."""
        self._vector_store = PGVector(
            embeddings=self._get_embeddings_model(),
            collection_name=COLLECTION_NAME,
            connection=DB_CONNECTION,
            use_jsonb=True,  # Tối ưu lưu trữ metadata (chunk_id, hierarchy...)
        )
        # Khởi tạo DB engine cho DocStore
        self._engine = create_engine(DB_CONNECTION)
        self._docstore = PostgresDocStore(self._engine)

    def _get_embeddings_model(self):
        return HuggingFaceEmbeddings(
            model_name=settings.huggingface_embedding_model,
            model_kwargs={'device': 'cpu'}, 
            encode_kwargs={'normalize_embeddings': True}
        )

    def add_documents(self, documents: List[Document]) -> None:
        """
        Thêm các chunks tài liệu vào PostgreSQL + pgvector.

        :param documents: Danh sách các Document chunks cần lưu
        """
        self._vector_store.add_documents(documents)

    def as_retriever(self, search_kwargs: dict = None) -> Any:
        """
        Trả về retriever object từ PGVector.

        :param search_kwargs: Dict chứa tham số tìm kiếm (ví dụ: {"k": 5})
        :return: Retriever object
        """
        if search_kwargs is None:
            search_kwargs = {"k": 4}
        return self._vector_store.as_retriever(search_kwargs=search_kwargs)

    def get_raw_vector_store(self) -> Any:
        """
        Trả về PGVector object thô (nếu cần truy cập trực tiếp, ví dụ cho BM25).

        :return: PGVector instance
        """
        return self._vector_store

    def get_hybrid_retriever(self, k: int = 5):
        """Trả về Custom Hybrid Retriever sử dụng cả Vector và FTS."""
        return PostgresHybridRetriever(
            connection_string=DB_CONNECTION,
            embeddings=self._get_embeddings_model(),
            top_k=k,
        )

    # ==========================================
    # PHẦN MỚI: CUNG CẤP PARENT DOCUMENT RETRIEVER
    # ==========================================
    def get_parent_document_retriever(self, file_ids: list[str] = None) -> HybridParentDocumentRetriever:
        """
        Trả về PDR object. Dùng chung cho cả Ingestion (Lưu DB) và Retrieval (Chat).
        Nếu có file_ids, sẽ tạo filter để chỉ search trong các file được chỉ định.
        """
        # Child splitter dùng để băm nhỏ dữ liệu lưu vào VectorDB
        child_splitter = RecursiveCharacterTextSplitter(
            chunk_size=400,
            chunk_overlap=50,
            separators=["\n\n", "\n", r"(?<=\. )", " ", ""],
        )

        search_kwargs = {}
        if file_ids is not None:
            if not file_ids:
                # Nếu được gọi với danh sách rỗng, ép trả về 0 kết quả
                search_kwargs["filter"] = {"file_id": {"$in": ["__NONE__"]}}
            else:
                # Tạo list ID hợp lệ bao gồm cả bản gốc và bản có .md (cho file cũ)
                valid_ids = []
                for f_id in file_ids:
                    clean_id = f_id.replace(".pdf", "").replace(".md", "")
                    valid_ids.extend([clean_id, f_id, f"{clean_id}.md"])
                search_kwargs["filter"] = {"file_id": {"$in": valid_ids}}

        base_retriever = HybridParentDocumentRetriever(
            vectorstore=self._vector_store,
            docstore=self._docstore,
            child_splitter=child_splitter,
            search_kwargs=search_kwargs,
            connection_string=DB_CONNECTION,
            embeddings=self._vector_store.embeddings,
            top_k=15 # Lấy 15 parent docs tốt nhất để đưa vào Cross-Encoder chấm điểm lại
        )
        
        from app.infrastructure.vector_store.reranker import CrossEncoderReranker, CrossEncoderRerankingRetriever
        reranker = CrossEncoderReranker(top_k=3)
        return CrossEncoderRerankingRetriever(
            base_retriever=base_retriever,
            reranker=reranker
        )

    def delete_documents_by_file_id(self, file_id: str) -> None:
        """Xóa toàn bộ các document (Embeddings và Docstore) liên quan đến file_id."""
        with self._engine.begin() as conn:
            # 1. Xóa trong bảng Embedding (chunks)
            # Chú ý: Một số file cũ được ingest bằng script ngoài có file_id chứa đuôi .md
            conn.execute(text("""
                DELETE FROM public.langchain_pg_embedding 
                WHERE cmetadata->>'file_id' IN (:id1, :id2)
            """), {"id1": file_id, "id2": f"{file_id}.md"})
            
            # 2. Xóa trong bảng DocStore (parent docs)
            conn.execute(text("""
                DELETE FROM public.langchain_pg_docstore 
                WHERE document->'metadata'->>'file_id' IN (:id1, :id2)
            """), {"id1": file_id, "id2": f"{file_id}.md"})
        
        print(f"🗑️ Đã xóa toàn bộ Vector Embeddings của file: {file_id}")

    def get_chunks_by_file_id(self, file_id: str) -> list[dict]:
        """Lấy toàn bộ các chunks (child chunks) của một file_id."""
        clean_id = file_id.replace(".pdf", "").replace(".md", "")
        with self._engine.begin() as conn:
            rows = conn.execute(text("""
                SELECT document, cmetadata FROM public.langchain_pg_embedding 
                WHERE cmetadata->>'file_id' IN (:id1, :id2, :id3)
            """), {"id1": file_id, "id2": f"{clean_id}.md", "id3": clean_id}).fetchall()
            
            return [{"content": row.document, "metadata": row.cmetadata} for row in rows]
