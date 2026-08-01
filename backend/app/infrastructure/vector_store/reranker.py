from typing import List
from langchain_core.documents import Document
from sentence_transformers import CrossEncoder

from functools import lru_cache

@lru_cache(maxsize=1)
def get_cross_encoder_model(model_name: str) -> CrossEncoder:
    print(f"Loading Cross-Encoder Reranker model into cache: {model_name}...")
    return CrossEncoder(model_name, max_length=512)

class CrossEncoderReranker:
    """
    Reranker sử dụng mô hình Cross-Encoder để chấm điểm độ liên quan trực tiếp 
    giữa câu hỏi (Query) và ngữ cảnh (Context / Document).
    """
    def __init__(
        self, 
        model_name: str = "unicamp-dl/mMiniLM-L6-v2-mmarco-v2", 
        top_k: int = 3
    ):
        self.model = get_cross_encoder_model(model_name)
        self.top_k = top_k

    def compress_documents(self, documents: List[Document], query: str) -> List[Document]:
        """
        Nhận vào danh sách Documents (từ Retriever trả về), 
        chấm điểm bằng CrossEncoder và trả về top_k documents tốt nhất.
        (Tuân theo Interface giống DocumentCompressor của LangChain)
        """
        if not documents:
            return []

        # Tạo input pairs: [[query, doc1_text], [query, doc2_text], ...]
        pairs = [[query, doc.page_content] for doc in documents]
        
        # CrossEncoder chấm điểm toàn bộ pairs
        scores = self.model.predict(pairs)
        
        # Gắn điểm vào metadata
        for i, doc in enumerate(documents):
            # Lưu ý không ghi đè metadata cũ
            doc.metadata["cross_encoder_score"] = float(scores[i])
            
        # Sắp xếp lại theo điểm Cross-Encoder giảm dần
        documents.sort(key=lambda x: x.metadata["cross_encoder_score"], reverse=True)
        
        return documents[:self.top_k]

from langchain_core.retrievers import BaseRetriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun

class CrossEncoderRerankingRetriever(BaseRetriever):
    """
    Retriever wrapper: Gọi base_retriever (như Hybrid Search) để lấy Top N documents,
    sau đó truyền qua CrossEncoderReranker để chấm điểm lại và trả về Top K.
    """
    base_retriever: BaseRetriever
    reranker: CrossEncoderReranker
    
    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> List[Document]:
        
        # 1. Gọi base retriever (Lấy 15 parent docs)
        docs = self.base_retriever.invoke(
            query, config={"callbacks": run_manager.get_child()}
        )
        
        # 2. Gọi reranker chấm điểm và cắt Top 3
        reranked_docs = self.reranker.compress_documents(docs, query)
        
        print(f"✅ RERANKER Đã chấm điểm {len(docs)} tài liệu, chọn ra top {len(reranked_docs)}")
        return reranked_docs

    def add_documents(self, documents: List[Document], **kwargs) -> List[str]:
        """
        Delegate add_documents to the underlying base_retriever 
        (e.g., ParentDocumentRetriever) so that document ingestion works normally.
        """
        if hasattr(self.base_retriever, "add_documents"):
            return self.base_retriever.add_documents(documents, **kwargs)
        raise NotImplementedError("base_retriever does not support add_documents")
