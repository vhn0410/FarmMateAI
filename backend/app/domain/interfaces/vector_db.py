from abc import ABC, abstractmethod
from typing import List, Any
from langchain_core.documents import Document


class IVectorStoreProvider(ABC):
    """
    Interface chuẩn cho mọi cơ sở dữ liệu Vector.
    Các implementation cụ thể (PGVector, Milvus, Weaviate, v.v.) phải implement các method này.
    """

    @abstractmethod
    def add_documents(self, documents: List[Document]) -> None:
        """Thêm các chunks tài liệu vào CSDL Vector."""
        pass

    @abstractmethod
    def as_retriever(self, search_kwargs: dict = None) -> Any:
        """
        Trả về retriever object để sử dụng trong RAG chains.

        :param search_kwargs: Dictionary chứa các tham số tìm kiếm (ví dụ: {"k": 5})
        :return: Retriever object
        """
        pass
