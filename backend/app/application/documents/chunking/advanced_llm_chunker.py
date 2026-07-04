import json
from typing import List
from concurrent.futures import ThreadPoolExecutor, as_completed
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.application.documents.chunking.base_chunker import IChunker
from app.core.config import settings


class AdvancedLLMChunker(IChunker):
    """
    Production-ready LLM-based Chunker (Propositional Chunking).
    Pipeline:
    1. Rough Splitting: Split text into ~10k character blocks.
    2. Proposition Extraction: Use gpt-4o-mini concurrently to extract atomic facts.
    3. (Optional in future) Semantic Clustering: Merge propositions.
    """

    def __init__(self, model_name="gpt-4o-mini", max_workers=5):
        self.rough_splitter = RecursiveCharacterTextSplitter(
            chunk_size=10000,
            chunk_overlap=500
        )
        self.llm = ChatOpenAI(
            model=model_name,
            api_key=settings.openai_api_key,
            base_url=settings.openai_api_base,
            temperature=0
        )
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", "Bạn là một AI phân tích văn bản siêu việt. Nhiệm vụ của bạn là đọc đoạn văn sau và trích xuất ra các 'Mệnh đề nguyên tử' (Atomic Propositions). Mỗi mệnh đề phải là một câu hoàn chỉnh, có đủ chủ ngữ vị ngữ, có ý nghĩa độc lập và mang thông tin quan trọng. Tuyệt đối không dùng đại từ nhân xưng mập mờ (như 'nó', 'việc đó', 'chúng') mà phải thay bằng danh từ rõ ràng.\nTrả về JSON chuẩn là một mảng các chuỗi. Chỉ trả về JSON."),
            ("user", "Đoạn văn:\n{text}")
        ])
        self.chain = self.prompt | self.llm
        self.max_workers = max_workers

    def _extract_propositions(self, text_block: str) -> List[str]:
        try:
            response = self.chain.invoke({"text": text_block})
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:-3]
            elif content.startswith("```"):
                content = content[3:-3]

            propositions = json.loads(content)
            if isinstance(propositions, list):
                return [p for p in propositions if isinstance(p, str) and p.strip()]
        except Exception as e:
            print(f"Lỗi extract proposition: {e}")
        # Fallback to simple split if LLM fails
        return [s.strip() for s in text_block.split('.') if s.strip()]

    def chunk(self, text: str, source: str = "Unknown") -> List[Document]:
        # 1. Rough splitting to avoid context limit and enable concurrency
        rough_docs = self.rough_splitter.split_text(text)
        print(
            f"Tiền xử lý: Cắt thô thành {len(rough_docs)} blocks. Bắt đầu gọi LLM...")

        all_propositions = []

        # 2. Concurrent Proposition Extraction
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_block = {executor.submit(
                self._extract_propositions, block): i for i, block in enumerate(rough_docs)}

            # Use an array to keep the original order
            results = [[] for _ in range(len(rough_docs))]

            for future in as_completed(future_to_block):
                i = future_to_block[future]
                try:
                    props = future.result()
                    results[i] = props
                except Exception as exc:
                    print(f"Block {i} sinh ra lỗi: {exc}")

        for res in results:
            all_propositions.extend(res)

        print(f"Hoàn thành: Trích xuất được {len(all_propositions)} mệnh đề.")

        # 3. Create Documents
        # Here we could run SemanticChunker over the propositions to merge them,
        # but returning atomic propositions is highly effective for RAG precision.
        # We will merge them into ~500 character chunks sequentially to avoid too many tiny vectors.
        merged_docs = []
        current_chunk = ""

        for prop in all_propositions:
            if len(current_chunk) + len(prop) > 600 and current_chunk:
                merged_docs.append(Document(page_content=current_chunk.strip(), metadata={
                                   "source": source, "chunk_type": "advanced_llm"}))
                current_chunk = prop
            else:
                current_chunk += " " + prop if current_chunk else prop

        if current_chunk:
            merged_docs.append(Document(page_content=current_chunk.strip(), metadata={
                               "source": source, "chunk_type": "advanced_llm"}))

        return merged_docs
