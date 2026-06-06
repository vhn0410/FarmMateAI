from typing import List, Any
from langchain_core.documents import Document
from app.domain.interfaces.vector_db import IVectorStoreProvider

from langchain_openai import OpenAIEmbeddings
from langchain_postgres import PGVector
from app.core.config import settings

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

    def _get_embeddings_model(self):
        return OpenAIEmbeddings(model="text-embedding-3-small", api_key=settings.openai_api_key)

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
