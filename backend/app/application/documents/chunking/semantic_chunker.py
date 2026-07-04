from typing import List
from langchain_core.documents import Document
from langchain_experimental.text_splitter import SemanticChunker
from langchain_huggingface import HuggingFaceEmbeddings
from app.application.documents.chunking.base_chunker import IChunker
from app.core.config import settings

class SemanticDocumentChunker(IChunker):
    def __init__(self, breakpoint_threshold_type="percentile", breakpoint_threshold_amount=95):
        # We use the same embeddings model used for indexing
        embeddings = HuggingFaceEmbeddings(
            model_name=settings.huggingface_embedding_model,
            model_kwargs={'device': 'cpu'}, 
            encode_kwargs={'normalize_embeddings': True}
        )
        self.splitter = SemanticChunker(
            embeddings, 
            breakpoint_threshold_type=breakpoint_threshold_type,
            breakpoint_threshold_amount=breakpoint_threshold_amount
        )

    def chunk(self, text: str, source: str = "Unknown") -> List[Document]:
        docs = self.splitter.create_documents([text])
        for doc in docs:
            doc.metadata["source"] = source
            doc.metadata["chunk_type"] = "semantic"
        return docs
