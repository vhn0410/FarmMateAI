from langchain_community.retrievers.bm25 import BM25Retriever
from langchain_classic.retrievers.ensemble import EnsembleRetriever
from langchain_core.documents import Document

from app.agents.skills.base import BaseSkill                    # Interface chuẩn từ Clean Architecture
from app.infrastructure.vector_store.pgvector_db import get_vector_store


class AgricultureRAGSkill(BaseSkill):
    name = "Tu_van_ky_thuat_nong_nghiep"
    description = (
        "Sử dụng công cụ này để trả lời các câu hỏi về nông nghiệp, môi trường đất, "
        "kỹ thuật canh tác và chất lượng nước. Đầu vào là câu hỏi của người dùng."
    )

    def __init__(self):
        self.vector_store = get_vector_store()

        # 1. Cấu hình Vector Retriever (Tìm theo ngữ nghĩa)
        self.vector_retriever = self.vector_store.as_retriever(search_kwargs={"k": 5})

        # 2. Cấu hình BM25 Retriever (Tìm theo Keyword)
        # Bắt buộc phải query lại toàn bộ DB để load data cho BM25 nếu dùng in-memory của Langchain
        # Lời khuyên của Senior: Lên Production nên đổi BM25 thành ElasticSearch
        # hoặc dùng PostgreSQL Full-Text Search để tối ưu RAM.
        all_docs = self._load_all_docs_from_db()
        if all_docs:
            self.bm25_retriever = BM25Retriever.from_documents(all_docs)
            self.bm25_retriever.k = 5

            # 3. Kết hợp thành Hybrid Search
            self.retriever = EnsembleRetriever(
                retrievers=[self.bm25_retriever, self.vector_retriever],
                weights=[0.5, 0.5],
            )
        else:
            # Fallback nếu DB trống
            self.retriever = self.vector_retriever

    def _load_all_docs_from_db(self) -> list[Document]:
        """Utility lấy toàn bộ chunks từ DB để build BM25 Index."""
        try:
            # Lấy thông qua connection sqlalchemy của pgvector (ví dụ tham khảo)
            # Ở môi trường thực tế, cẩn thận tràn RAM nếu có hàng triệu chunks.
            with self.vector_store._make_session() as session:
                records = session.query(self.vector_store.EmbeddingStore).all()
                return [
                    Document(page_content=r.document, metadata=r.cmetadata)
                    for r in records
                ]
        except Exception as e:
            print(f"Cảnh báo: Không thể nạp dữ liệu cho BM25: {e}")
            return []

    def run(self, query: str, **kwargs) -> str:
        """Thực thi lấy context cho LLM."""
        try:
            docs = self.retriever.invoke(query)

            if not docs:
                return "Ngữ cảnh không cung cấp đủ thông tin về vấn đề này."

            # Ghép nối nội dung và hierarchy để truyền cho Agent
            context_pieces = []
            for doc in docs:
                hierarchy = doc.metadata.get("document_hierarchy", "")
                context_pieces.append(f"[Mục: {hierarchy}]\n{doc.page_content}")

            # Trả về context thuần túy. "Bộ não" Agent sẽ nhận string này,
            # áp dụng System Prompt (Bước 5 trong Notebook của bạn) để suy luận câu trả lời.
            return "\n\n---\n\n".join(context_pieces)

        except Exception as e:
            return f"[Lỗi truy xuất hệ thống: {str(e)}]"
