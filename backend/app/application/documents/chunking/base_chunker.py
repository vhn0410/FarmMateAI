from abc import ABC, abstractmethod
from typing import List
from langchain_core.documents import Document

class IChunker(ABC):
    """
    Interface for document chunking strategies.
    """
    @abstractmethod
    def chunk(self, text: str, source: str = "Unknown") -> List[Document]:
        """
        Splits text into chunks and returns a list of Document objects.
        """
        pass
