from langchain_community.retrievers.bm25 import BM25Retriever
from langchain_classic.retrievers.ensemble import EnsembleRetriever
from langchain_core.documents import Document

from app.agents.skills.base import BaseSkill                    # Interface chuẩn từ Clean Architecture
from app.infrastructure.vector_store.pgvector_db import get_vector_store
from app.infrastructure.llm.openai_client import get_llm
from langchain_core.prompts import ChatPromptTemplate
from langchain_classic.chains.combine_documents import (
    create_stuff_documents_chain,
)
from langchain_classic.chains import create_retrieval_chain

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
            print(f"Đã nạp {len(all_docs)} tài liệu cho BM25 Retriever.")
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
        
        # ==========================================
        # TÍCH HỢP PROMPT CHỐNG SUY DIỄN
        # ==========================================
        llm = get_llm(model="gpt-4o-mini", temperature=0.0)
        # Bê nguyên đoạn prompt xuất sắc của bạn từ notebook vào đây
        system_prompt = (
            """Bạn là chuyên gia phân tích tài liệu khoa học. Nhiệm vụ của bạn là trả lời câu hỏi DỰA HOÀN TOÀN vào ngữ cảnh được cung cấp.
            Quy tắc bắt buộc:
            1. KHÔNG SUY DIỄN: Chỉ sử dụng thông tin có trong ngữ cảnh. Không thêm kiến thức bên ngoài, không tự ý giải thích hoặc kết luận nếu ngữ cảnh không ghi rõ.
            2. ĐỐI SÁNH SỐ LIỆU CHÍNH XÁC (QUAN TRỌNG):
               - Khi ngữ cảnh liệt kê danh sách (ví dụ: A, B, C có giá trị lần lượt là X, Y, Z), BẠN PHẢI ghép đúng đối tượng với số liệu tương ứng. Tuyệt đối không hoán đổi số liệu của đối tượng này cho đối tượng khác.
               - Không tự ý làm tròn số liệu.
            3. XỬ LÝ DỮ LIỆU MÂU THUẪN:
               - Nếu ngữ cảnh có nhiều giá trị khác nhau cho cùng một đối tượng ở các đoạn khác nhau, hãy ưu tiên trích xuất chính xác theo đúng cụm từ/câu chứa thông tin phân loại đó, hoặc nêu rõ cả hai nếu cần thiết. KHÔNG tự ý gộp số liệu.
            4. CHỈ TRÍCH XUẤT ĐỀ XUẤT CÓ SẴN: Nếu ngữ cảnh đề cập giải pháp/đề xuất, chỉ nêu đúng những gì được viết, không tự nghĩ thêm.
            5. XỬ LÝ KHI THIẾU THÔNG TIN: Nếu không đủ thông tin để trả lời, hãy nói rõ: 'Ngữ cảnh không cung cấp đủ thông tin về vấn đề này.'
            6. HÌNH THỨC: Câu trả lời cần súc tích, cấu trúc rõ ràng (nhận định → số liệu trích dẫn cụ thể → đề xuất nếu có).

            Ngữ cảnh: {context}"""
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", "{input}"),
        ])

        # Khởi tạo RAG Chain nội bộ cho Skill này
        document_qa_chain = create_stuff_documents_chain(llm, prompt)
        self.qa_chain = create_retrieval_chain(self.retriever, document_qa_chain)


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
        """
        Thực thi RAG Chain. Thay vì trả về raw text, Skill này trả về luôn câu trả lời 
        đã được nhào nặn chặt chẽ bởi prompt không suy diễn.
        """
        try:
            # Lưu ý key "input" để khớp với format của create_retrieval_chain
            result = self.qa_chain.invoke({"input": query})
            
            # Lấy câu trả lời chính thức từ chuỗi
            final_answer = result.get("answer", "")
            return final_answer
            
        except Exception as e:
            return f"[Lỗi truy xuất hệ thống: {str(e)}]"
