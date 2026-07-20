import time
import logging
from typing import List
from concurrent.futures import ThreadPoolExecutor, as_completed
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.core.config import settings

logger = logging.getLogger(__name__)

class LLMDocumentCleaner:
    """
    Sử dụng LLM tốc độ cao (gpt-4o-mini) để dọn dẹp các rác sinh ra từ PDF (Header/Footer, số trang).
    Chạy xử lý song song (Concurrency) để tối ưu thời gian.
    """
    def __init__(self, model_name="gpt-4o-mini", max_workers=1):
        self.llm = ChatOpenAI(
            model=model_name,
            api_key=settings.openai_api_key,
            base_url=settings.openai_api_base,
            temperature=0
        )
        self.max_workers = max_workers
        
        # Prompt ép LLM chỉ dọn rác, không bịa nội dung, không tóm tắt
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", 
             "Bạn là một chuyên gia xử lý văn bản Markdown. Nhiệm vụ của bạn là làm sạch đoạn văn bản được trích xuất từ file PDF.\n"
             "Quy tắc tuyệt đối:\n"
             "1. XÓA BỎ toàn bộ các Header (tiêu đề đầu trang), Footer (tiêu đề cuối trang), số trang, ngày tháng hoặc các đoạn text rác lặp lại vô nghĩa (VD: 'SỔ TAY HƯỚNG DẪN', 'Trang 15').\n"
             "2. NỐI LẠI các câu bị đứt gãy do ngắt trang.\n"
             "3. GIỮ NGUYÊN cấu trúc Markdown ban đầu (tiêu đề, in đậm, danh sách).\n"
             "4. KHÔNG ĐƯỢC thay đổi ngữ nghĩa, KHÔNG ĐƯỢC tóm tắt, KHÔNG ĐƯỢC tự thêm thông tin.\n"
             "Chỉ trả về văn bản Markdown đã được làm sạch, không thêm bất kỳ bình luận nào khác."
             ),
            ("user", "Văn bản gốc:\n{text}")
        ])
        
        self.chain = self.prompt | self.llm

    def _clean_single_document(self, doc: Document, index: int, total: int) -> Document:
        """Làm sạch 1 Document."""
        print(f"Đang dọn rác chunk {index+1}/{total}...", flush=True)
        time.sleep(1) # Rate limit avoidance
        for attempt in range(5):
            try:
                if not doc.page_content.strip():
                    return doc
                    
                response = self.chain.invoke({"text": doc.page_content})
                cleaned_text = response.content.strip()
                
                # Giữ nguyên Metadata
                return Document(page_content=cleaned_text, metadata=doc.metadata.copy())
            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg or "Too Many Requests" in error_msg or "RateLimitError" in error_msg:
                    sleep_time = 4 ** attempt
                    print(f"Rate limit hit (429) ở chunk {index+1}. Retrying in {sleep_time}s... (Attempt {attempt+1}/5)", flush=True)
                    time.sleep(sleep_time)
                else:
                    print(f"Lỗi khi clean document {index+1}: {e}", flush=True)
                    return doc # Nếu lỗi khác thì trả về doc gốc (Fallback)
        print(f"Đã hết số lần thử lại (5 lần) cho chunk {index+1}. Fallback về doc gốc.", flush=True)
        return doc

    def clean_documents(self, docs: List[Document]) -> List[Document]:
        """
        Làm sạch danh sách Document bằng xử lý đa luồng (Concurrency).
        Đảm bảo giữ đúng thứ tự ban đầu của mảng Document.
        """
        if not docs:
            return []
            
        print(f"Bắt đầu quy trình LLM Cleanup cho {len(docs)} chunks...", flush=True)
        results = [None] * len(docs)
        total_docs = len(docs)
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Map index vào Future để khi nhận kết quả có thể điền lại đúng vị trí
            future_to_index = {
                executor.submit(self._clean_single_document, doc, i, total_docs): i 
                for i, doc in enumerate(docs)
            }
            
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    cleaned_doc = future.result()
                    results[index] = cleaned_doc
                except Exception as exc:
                    print(f"Chunk thứ {index+1} sinh ra exception: {exc}", flush=True)
                    results[index] = docs[index] # Fallback
                    
        # Lọc ra các Document hợp lệ (có nội dung)
        final_docs = [doc for doc in results if doc and doc.page_content.strip()]
        print(f"LLM Cleanup hoàn tất. Giữ lại {len(final_docs)} chunks sạch.", flush=True)
        return final_docs
