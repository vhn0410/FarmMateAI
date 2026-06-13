import logging
from typing import Optional, Dict

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_classic.chains import create_retrieval_chain
from langchain_community.callbacks.manager import get_openai_callback

from app.agents.skills.base import BaseSkill, SkillResult
from app.domain.interfaces.vector_db import IVectorStoreProvider
from app.domain.interfaces.llm_provider import ILLMProvider


class AgricultureRAGSkill(BaseSkill):
    name = "Tu_van_ky_thuat_nong_nghiep"
    description = (
        "Sử dụng công cụ này để trả lời các câu hỏi về nông nghiệp, môi trường đất, "
        "kỹ thuật canh tác và chất lượng nước. Đầu vào là câu hỏi của người dùng."
    )

    def __init__(
        self, vector_store_provider: IVectorStoreProvider, llm_provider: ILLMProvider
    ):
        """
        Khởi tạo Agriculture RAG Skill với Dependency Injection.

        :param vector_store_provider: Implementation của IVectorStoreProvider
        :param llm_provider: Implementation của ILLMProvider
        """
        self.vector_store_provider = vector_store_provider
        self.llm_provider = llm_provider

        # Khởi tạo Hybrid Retriever CỰC KỲ GỌN NHẸ
        # logging.info("Đang khởi tạo Postgres Hybrid Retriever (Vector + FTS)...")
        # self.retriever = self.vector_store_provider.get_hybrid_retriever(k=10)
        # Khởi tạo Parent document Retriever
        logging.info(
            "Đang khởi tạo Postgres Parent document Retriever (Vector + FTS)..."
        )
        self.retriever = self.vector_store_provider.get_parent_document_retriever()

        # ==========================================
        # TÍCH HỢP PROMPT CHỐNG SUY DIỄN
        # ==========================================
        llm = self.llm_provider.get_llm()

        system_prompt = """Bạn là chuyên gia phân tích tài liệu khoa học. Nhiệm vụ của bạn là trả lời câu hỏi DỰA HOÀN TOÀN vào ngữ cảnh được cung cấp.
            Quy tắc bắt buộc:
            1. KHÔNG SUY DIỄN: Chỉ sử dụng thông tin có trong ngữ cảnh. Không thêm kiến thức bên ngoài, không tự ý giải thích hoặc kết luận nếu ngữ cảnh không ghi rõ.
            2. ĐỐI SÁNH SỐ LIỆU CHÍNH XÁC (QUAN TRỌNG):
               - Khi ngữ cảnh liệt kê danh sách (ví dụ: A, B, C có giá trị lần lượt là X, Y, Z), BẠN PHẢI ghép đúng đối tượng với số liệu tương ứng. Tuyệt đối không hoán đổi số liệu của đối tượng này cho đối tượng khác.
               - Không tự ý làm tròn số liệu.
            3. XỬ LÝ DỮ LIỆU MÂU THUẪN:
               - Nếu ngữ cảnh có nhiều giá trị khác nhau cho cùng một đối tượng ở các đoạn khác nhau, hãy ưu tiên trích xuất chính xác theo đúng cụm từ/câu chứa thông tin phân loại đó, hoặc nêu rõ cả hai nếu cần thiết. KHÔNG tự ý gộp số liệu.
            4. CHỈ TRÍCH XUẤT ĐỀ XUẤT CÓ SẴN: Nếu ngữ cảnh đề cập giải pháp/đề xuất, chỉ nêu đúng những gì được viết, không tự nghĩ thêm.
            5. XỬ LÝ CÂU HỎI MẬP MỜ/TỪ KHÓA: Nếu đầu vào của người dùng chỉ là một vài từ khóa ngắn (ví dụ: tên địa danh, tên cây trồng) mà không phải một câu hỏi rõ ràng, hãy tóm tắt những thông tin quan trọng nhất mà ngữ cảnh nhắc đến về các từ khóa đó.
            6. XỬ LÝ KHI THIẾU THÔNG TIN: Nếu không đủ thông tin để trả lời, hãy nói rõ: 'Ngữ cảnh không cung cấp đủ thông tin về vấn đề này.'
            7. HÌNH THỨC: Câu trả lời cần súc tích, cấu trúc rõ ràng (nhận định → số liệu trích dẫn cụ thể → đề xuất nếu có).

            Ngữ cảnh: {context}"""

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                ("user", "{input}"),
            ]
        )

        # Khởi tạo RAG Chain nội bộ cho Skill này
        document_qa_chain = create_stuff_documents_chain(llm, prompt)
        self.qa_chain = create_retrieval_chain(self.retriever, document_qa_chain)

    def _load_all_docs_from_db(self) -> list[Document]:
        """Utility lấy toàn bộ chunks từ DB để build BM25 Index."""
        print("Đang nạp dữ liệu từ DB cho BM25 Retriever...")
        try:
            # Lấy raw vector store để truy cập PGVector internals
            vector_store = self.vector_store_provider.get_raw_vector_store()

            with vector_store._make_session() as session:
                records = session.query(vector_store.EmbeddingStore).all()
                print(f"Truy vấn DB thành công, nạp {len(records)} bản ghi cho BM25.")
                return [
                    Document(page_content=r.document, metadata=r.cmetadata)
                    for r in records
                ]
        except Exception as e:
            print(f"Cảnh báo: Không thể nạp dữ liệu cho BM25: {e}")
            return []

    def run(self, query: str, **kwargs) -> SkillResult:
        """
        Thực thi RAG Chain và capture metadata (sources, tokens, actions).
        Đã FIX lỗi Double Fetch: Chỉ gọi qa_chain 1 lần duy nhất.
        """
        agent_actions = []
        tokens_used: Optional[Dict[str, int]] = None
        sources = []

        try:
            agent_actions.append(f"Invoking QA Chain for query: '{query[:50]}...'")

            # ===== STEP 1: GỌI QA CHAIN NGAY LẬP TỨC (Chỉ 1 lần gọi DB) =====
            with get_openai_callback() as cb:
                # Lệnh này sẽ tự động search DB và sinh câu trả lời
                result = self.qa_chain.invoke({"input": query})

                if cb.total_tokens > 0:
                    tokens_used = {
                        "prompt_tokens": cb.prompt_tokens,
                        "completion_tokens": cb.completion_tokens,
                        "total_tokens": cb.total_tokens,
                    }
                    agent_actions.append(
                        f"Consumed {cb.total_tokens} tokens from LLM "
                        f"(prompt: {cb.prompt_tokens}, completion: {cb.completion_tokens})"
                    )

            # ===== STEP 2: LẤY CÂU TRẢ LỜI VÀ TÀI LIỆU TỪ RESULT =====
            final_answer = result.get("answer", "Không có câu trả lời.")
            # create_retrieval_chain luôn trả về tài liệu tìm được trong key "context"
            retrieved_docs = result.get("context", [])

            agent_actions.append(
                f"Retrieved {len(retrieved_docs)} documents from vector store internally."
            )

            # ===== STEP 3: TRÍCH XUẤT METADATA =====
            for idx, doc in enumerate(retrieved_docs[:5]):  # Top 5 docs
                metadata = doc.metadata or {}
                source_obj = {
                    "doc_index": idx,
                    "file_name": metadata.get("file_name", "Unknown"),
                    "hierarchy": metadata.get("document_hierarchy", "Unknown"),
                    "content_snippet": doc.page_content[:200],  # Dành cho UI
                    "full_content": doc.page_content,  # Dành cho Evaluation
                    "chunk_id": metadata.get("chunk_id", ""),
                }
                sources.append(source_obj)

            agent_actions.append("Answer generation and source extraction complete")

            # ===== STEP 4: RETURN SkillResult =====
            return SkillResult(
                answer=final_answer,
                skill_name=self.name,
                metadata={
                    "sources": sources,
                    "retrieved_docs_count": len(retrieved_docs),
                    "top_sources": sources[:3],
                },
                tokens_used=tokens_used,
                agent_actions=agent_actions,
            )

        except Exception as e:
            error_msg = f"[Lỗi truy xuất hệ thống: {str(e)}]"
            import traceback

            agent_actions.append(f"Error occurred: {str(e)}")
            agent_actions.append(f"Traceback: {traceback.format_exc()[:100]}")
            return SkillResult(
                answer=error_msg,
                skill_name=self.name,
                metadata={
                    "sources": [],
                    "retrieved_docs_count": 0,
                    "top_sources": [],
                },
                tokens_used=tokens_used,
                agent_actions=agent_actions,
            )
