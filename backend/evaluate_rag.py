import os
import sys
import json
import csv
import asyncio
from typing import List, Dict, Any
from pydantic import BaseModel, Field

# Fix Windows encoding issue
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Thêm đường dẫn backend vào sys.path để import được các module của app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.infrastructure.llm.openai_client import OpenAIClient
from app.infrastructure.vector_store.pgvector_provider import PGVectorProvider
from app.infrastructure.vector_store.graph_provider import Neo4jGraphProvider
from langchain_core.prompts import ChatPromptTemplate

# --- 1. Dataset ---
GOLDEN_DATASET = [
    # {
    #     "id": 1,
    #     "type": "Multi-hop",
    #     "query": "Tình trạng xâm nhập mặn ở ĐBSCL dẫn đến việc người ta lai tạo lúa mang đặc tính gì để trồng kết hợp với dinh dưỡng?"
    # },
    # {
    #     "id": 2,
    #     "type": "Global Summarization",
    #     "query": "Liệt kê tất cả các giống lúa dinh dưỡng được đề cập và lợi ích y tế cụ thể của từng giống."
    # },
    # {
    #     "id": 3,
    #     "type": "Conditional / Edge Property",
    #     "query": "Điều kiện nào làm suy thoái lớp đất phù sa ở ĐBSCL và buộc người ta phải dùng đến quản lý dinh dưỡng tổng hợp?"
    # },
    # {
    #     "id": 4,
    #     "type": "Multi-hop / Intersection",
    #     "query": "Giữa giống Lúa Thơm Tiêu Chuẩn (OM5451) và Giống có GI Thấp, có điểm chung nào về vùng trồng và kỹ thuật tưới tiêu không?"
    # },
    # {
    #     "id": 5,
    #     "type": "Multi-hop / Intersection",
    #     "query": "Công ty nào sản xuất loại phân bón dùng để giải quyết tình trạng suy thoái đất do canh tác 3 vụ liên tục ở ĐBSCL?"
    # },
    {
        "id": 6,
        "type": "Information Fusion",
        "query": "Kể tên tất cả các sản phẩm (bao gồm phân bón, thuốc bảo vệ thực vật sinh học, và các giống lúa) được sản xuất hoặc phân phối bởi công ty có hoạt động tại Đồng Tháp và Sóc Trăng?"
    }
]

# --- 2. LLM Judge Schema ---
class EvaluationScore(BaseModel):
    faithfulness: int = Field(description="Score from 1-10 on how factual and non-hallucinated the answer is based on the context.")
    comprehensiveness: int = Field(description="Score from 1-10 on how fully the answer addresses the question.")
    reasoning: int = Field(description="Score from 1-10 on how well the answer connects multiple pieces of information.")
    explanation: str = Field(description="A brief explanation for the scores.")

# --- 3. Evaluator Class ---
class RAGEvaluator:
    def __init__(self):
        self.llm_provider = OpenAIClient(model="gpt-4o")
        self.llm = self.llm_provider.get_llm()
        self.vector_db = PGVectorProvider()
        self.graph_db = Neo4jGraphProvider()
        
        self.rag_prompt = ChatPromptTemplate.from_messages([
            ("system", "Bạn là một chuyên gia nông nghiệp phân tích dữ liệu. Hãy trả lời câu hỏi của người dùng DỰA HOÀN TOÀN VÀO BỐI CẢNH (Context) được cung cấp dưới đây. Nếu bối cảnh không chứa câu trả lời, hãy nói 'Tôi không biết'.\n\n[Bối cảnh]:\n{context}"),
            ("user", "Câu hỏi: {question}")
        ])
        
        self.judge_prompt = ChatPromptTemplate.from_messages([
            ("system", "Bạn là một Giám khảo AI công tâm. Nhiệm vụ của bạn là chấm điểm câu trả lời của 2 hệ thống (Naive RAG và Graph RAG) dựa trên Câu hỏi của người dùng.\n\nCâu hỏi: {question}\n\n[Câu trả lời cần chấm điểm]:\n{answer}"),
            ("user", "Hãy chấm điểm theo cấu trúc được yêu cầu.")
        ])

    def retrieve_naive_context(self, query: str) -> str:
        """Retrieves only from Vector DB"""
        retriever = self.vector_db.get_parent_document_retriever()
        docs = retriever.invoke(query)
        context = "\n\n".join([d.page_content for d in docs])
        return context

    def retrieve_graph_context(self, query: str) -> str:
        """Retrieves from Vector DB + Graph DB"""
        retriever = self.vector_db.get_parent_document_retriever()
        docs = retriever.invoke(query)
        vector_context = "\n\n".join([d.page_content for d in docs])
        
        graph_context = self.graph_db.query_graph_context(query)
        if not graph_context:
            graph_context = ""
            
        combined_context = f"=== VECTOR CONTEXT ===\n{vector_context}\n\n=== GRAPH CONTEXT ===\n{graph_context}"
        return combined_context

    def generate_answer(self, query: str, context: str) -> str:
        chain = self.rag_prompt | self.llm
        result = chain.invoke({"question": query, "context": context})
        return result.content
        
    def judge_answer(self, query: str, answer: str) -> EvaluationScore:
        chain = self.judge_prompt | self.llm.with_structured_output(EvaluationScore)
        result = chain.invoke({"question": query, "answer": answer})
        return result

    def run_evaluation(self, output_csv: str = "rag_evaluation_results.csv"):
        print(f"Bat dau danh gia (A/B Testing) tren {len(GOLDEN_DATASET)} cau hoi...\n")
        
        results = []
        
        for item in GOLDEN_DATASET:
            q_id = item["id"]
            q_type = item["type"]
            query = item["query"]
            
            print(f"[{q_id}] Dang danh gia cau hoi ({q_type}): {query}")
            
            # --- NAIVE RAG ---
            naive_ctx = self.retrieve_naive_context(query)
            naive_ans = self.generate_answer(query, naive_ctx)
            naive_score = self.judge_answer(query, naive_ans)
            
            # --- GRAPH RAG ---
            graph_ctx = self.retrieve_graph_context(query)
            graph_ans = self.generate_answer(query, graph_ctx)
            graph_score = self.judge_answer(query, graph_ans)
            
            # Save results
            results.append({
                "ID": q_id,
                "Type": q_type,
                "Question": query,
                "Naive_Answer": naive_ans,
                "Naive_Faithfulness": naive_score.faithfulness,
                "Naive_Comprehensiveness": naive_score.comprehensiveness,
                "Naive_Reasoning": naive_score.reasoning,
                "Naive_Total": naive_score.faithfulness + naive_score.comprehensiveness + naive_score.reasoning,
                "Graph_Answer": graph_ans,
                "Graph_Faithfulness": graph_score.faithfulness,
                "Graph_Comprehensiveness": graph_score.comprehensiveness,
                "Graph_Reasoning": graph_score.reasoning,
                "Graph_Total": graph_score.faithfulness + graph_score.comprehensiveness + graph_score.reasoning,
                "Judge_Explanation_Naive": naive_score.explanation,
                "Judge_Explanation_Graph": graph_score.explanation
            })
            
            print(f"  - Naive RAG Score: {results[-1]['Naive_Total']}/30")
            print(f"  - Graph RAG Score: {results[-1]['Graph_Total']}/30\n")
            
        # Write to CSV
        print(f"Dang luu vao file {output_csv}...")
        keys = results[0].keys()
        with open(output_csv, 'w', newline='', encoding='utf-8') as f:
            dict_writer = csv.DictWriter(f, keys)
            dict_writer.writeheader()
            dict_writer.writerows(results)
            
        print("Hoan tat!")

if __name__ == "__main__":
    evaluator = RAGEvaluator()
    evaluator.run_evaluation()
