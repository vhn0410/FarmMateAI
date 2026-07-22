import sys
import json
import time
import argparse
from pathlib import Path
from typing import List, Dict

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.append(str(Path(__file__).resolve().parent.parent))

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.core.config import settings
from app.infrastructure.vector_store.pgvector_provider import PGVectorProvider
from app.infrastructure.vector_store.graph_provider import Neo4jGraphProvider

LLM = ChatOpenAI(model="gpt-4o-mini", api_key=settings.openai_api_key, base_url=settings.openai_api_base, temperature=0)

def evaluate_retrieved_context(question: str, ground_truth: str, context: str) -> Dict[str, float]:
    # 1. Evaluate Precision
    precision_prompt = ChatPromptTemplate.from_messages([
        ("system", "Đánh giá mức độ liên quan của ngữ cảnh được cung cấp so với câu hỏi. Ngữ cảnh có chứa thông tin để trả lời câu hỏi không? Trả lời bằng JSON: {{\"score\": 1}} nếu có chứa thông tin để trả lời trực tiếp, {{\"score\": 0}} nếu hoàn toàn lạc đề hoặc {{\"score\": 0.5}} nếu có liên quan nhưng không giải quyết trực tiếp câu hỏi. Chỉ trả về JSON."),
        ("user", "Câu hỏi: {question}\nNgữ cảnh:\n{context}")
    ])
    p_resp = (precision_prompt | LLM).invoke({"question": question, "context": context})
    p_content = p_resp.content.strip()
    if p_content.startswith("```json"): p_content = p_content[7:-3]
    elif p_content.startswith("```"): p_content = p_content[3:-3]
    try:
        precision_score = float(json.loads(p_content).get("score", 0))
    except:
        precision_score = 0
        
    # 2. Evaluate Recall
    recall_prompt = ChatPromptTemplate.from_messages([
        ("system", "So sánh Ngữ cảnh được cung cấp với Câu trả lời tham chiếu. Ngữ cảnh có bao phủ đủ các ý chính của Câu trả lời tham chiếu không? Trả lời bằng JSON: {{\"score\": 1}} nếu đủ 100% ý chính, {{\"score\": 0.5}} nếu chỉ có một phần ý chính, {{\"score\": 0}} nếu không có ý nào. Chỉ trả về JSON."),
        ("user", "Câu trả lời tham chiếu:\n{ground_truth}\n\nNgữ cảnh:\n{context}")
    ])
    r_resp = (recall_prompt | LLM).invoke({"ground_truth": ground_truth, "context": context})
    r_content = r_resp.content.strip()
    if r_content.startswith("```json"): r_content = r_content[7:-3]
    elif r_content.startswith("```"): r_content = r_content[3:-3]
    try:
        recall_score = float(json.loads(r_content).get("score", 0))
    except:
        recall_score = 0
        
    return {"precision": precision_score, "recall": recall_score}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True, help="Tên file markdown")
    args = parser.parse_args()
    
    gold_qa_file = Path("evaluate/gold_qa") / f"{Path(args.file).stem}_gold_qa.json"
    if not gold_qa_file.exists():
        print(f"Chưa có bộ Gold QA: {gold_qa_file}.")
        sys.exit(1)
        
    with open(gold_qa_file, "r", encoding="utf-8") as f:
        qa_pairs = json.load(f)[:5]
        
    print(f"Đã nạp {len(qa_pairs)} câu hỏi đánh giá (giới hạn 5 câu).")
    
    print("Đang khởi tạo PGVector Provider (Baseline Hybrid + Reranker)...")
    pg_provider = PGVectorProvider()
    vector_retriever = pg_provider.get_parent_document_retriever(file_ids=[args.file, f"{args.file}.md"])
    
    print("Đang khởi tạo Neo4j Graph Provider...")
    graph_provider = Neo4jGraphProvider()
    
    methods = ["Baseline: Pure Vector RAG", "Pure Graph RAG", "Parallel Graph + Vector RAG"]
    results = {m: {"Time (s)": 0, "Precision": 0, "Recall": 0} for m in methods}
    
    for name in methods:
        print(f"\n--- Đang đánh giá {name} ---")
        
        total_precision = 0
        total_recall = 0
        start_time = time.time()
        
        for idx, qa in enumerate(qa_pairs):
            q = qa['question']
            a = qa['answer']
            
            context = ""
            
            try:
                # Retrieve context based on method
                if name == "Baseline: Pure Vector RAG":
                    docs = vector_retriever.invoke(q)[:3]
                    context = "\n\n".join([d.page_content for d in docs])
                elif name == "Pure Graph RAG":
                    context = graph_provider.query_graph_context(q)
                elif name == "Parallel Graph + Vector RAG":
                    docs = vector_retriever.invoke(q)[:3]
                    vec_ctx = "\n\n".join([d.page_content for d in docs])
                    graph_ctx = graph_provider.query_graph_context(q)
                    context = f"Graph Facts:\n{graph_ctx}\n\nVector Excerpts:\n{vec_ctx}"
                
                scores = evaluate_retrieved_context(q, a, context)
                total_precision += scores['precision']
                total_recall += scores['recall']
                
                print(f"  Q{idx+1}/{len(qa_pairs)}: Precision: {scores['precision']}, Recall: {scores['recall']}")
            except Exception as e:
                print(f"  Q{idx+1}/{len(qa_pairs)} Lỗi khi đánh giá: {e}")
                time.sleep(5)
                
            time.sleep(1.0) # Avoid Rate Limit
            
        elapsed_time = time.time() - start_time
        
        avg_precision = total_precision / len(qa_pairs) if qa_pairs else 0
        avg_recall = total_recall / len(qa_pairs) if qa_pairs else 0
        
        results[name]["Time (s)"] = round(elapsed_time, 2)
        results[name]["Precision"] = round(avg_precision * 100, 2)
        results[name]["Recall"] = round(avg_recall * 100, 2)
        
    # Write Report
    report_lines = [
        "# Báo cáo Đánh giá Graph RAG so với Standard RAG",
        f"**File test:** {args.file}",
        f"**Số lượng câu hỏi (Gold QA):** {len(qa_pairs)}",
        "**Top K Retrieve (Vector):** 3",
        "",
        "| Phương pháp Truy xuất | Thời gian đánh giá (s) | Precision (%) | Recall (%) |",
        "|-----------------------|------------------------|---------------|------------|"
    ]
    
    for name, data in results.items():
        report_lines.append(
            f"| {name} | {data['Time (s)']} | **{data['Precision']}%** | **{data['Recall']}%** |"
        )
        
    report_content = "\n".join(report_lines)
    report_path = Path("evaluate/results/graph_rag/graph_rag_evaluation_report.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)
        
    print(f"\n✅ Đã xuất báo cáo tại: {report_path.resolve()}")

if __name__ == "__main__":
    main()
