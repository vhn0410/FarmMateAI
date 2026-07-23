from abc import ABC, abstractmethod
from typing import List
from langchain_core.documents import Document


class IDocumentProvider(ABC):
    """
    Standard interface for all external document providers.
    """

    @abstractmethod
    def fetch_new_documents(self) -> List[Document]:
        """Fetch a list of new, unprocessed documents."""
        pass

    @abstractmethod
    def mark_as_processed(self, file_id: str) -> None:
        """Mark a document as successfully processed."""
        pass

    @abstractmethod
    def check_pdf_exists(self, file_name: str) -> bool:
        """Check if a PDF file exists."""
        pass

    @abstractmethod
    def create_lock(self, file_id: str) -> None:
        """Create a processing lock for a file to prevent deletion."""
        pass

    @abstractmethod
    def remove_lock(self, file_id: str) -> None:
        """Remove the processing lock for a file."""
        pass

    @abstractmethod
    def is_locked(self, file_id: str) -> bool:
        """Check if a file is currently locked for processing."""
        pass
