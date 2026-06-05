from abc import ABC, abstractmethod
from typing import List
from langchain_core.documents import Document


class IDocumentProvider(ABC):
    """
    Interface chuẩn cho mọi dịch vụ cung cấp tài liệu từ bên ngoài.
    Dù sau này dùng Google Drive, AWS S3, hay Dropbox thì đều phải tuân thủ hợp đồng này.
    """

    @abstractmethod
    def fetch_new_documents(self) -> List[Document]:
        """Lấy danh sách các tài liệu mới chưa được xử lý."""
        pass

    @abstractmethod
    def mark_as_processed(self, file_id: str) -> None:
        """Đánh dấu một tài liệu đã được xử lý xong."""
        pass
