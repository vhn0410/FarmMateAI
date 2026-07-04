import os
import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict

# Fix windows console encoding issue
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# Set up paths so we can import from app
sys.path.append(str(Path(__file__).resolve().parent.parent))

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

from app.core.config import settings
from app.application.documents.chunking.parent_document_chunker import ParentDocumentChunker
from app.application.documents.chunking.semantic_chunker import SemanticDocumentChunker
from app.application.documents.chunking.advanced_llm_chunker import AdvancedLLMChunker

LLM = ChatOpenAI(model="gpt-4o-mini", api_key=settings.openai_api_key, base_url=settings.openai_api_base, temperature=0)

def generate_ground_truth(text: str, num_questions: int = 5) -> List[Dict]:
    print(f"Bắt đầu sinh {num_questions} câu hỏi Ground Truth từ văn bản...")
    prompt = ChatPromptTemplate.from_messages([
        ("system", "Bạn là một chuyên gia đánh giá hệ thống RAG. Dựa vào văn bản dưới đây, hãy tạo ra đúng {num_questions} cặp Câu hỏi (question) và Câu trả lời (answer) dựa trên thông tin có trong văn bản.\nTrả về JSON chuẩn có cấu trúc: [ {{\"question\": \"...\", \"answer\": \"...\"}} ]\nChỉ trả về mảng JSON, không giải thích."),
        ("user", "Văn bản:\n{text}")
    ])
    chain = prompt | LLM
    # If text is too long, just take first 10000 chars to generate questions
    response = chain.invoke({"text": text[:10000], "num_questions": num_questions})
    content = response.content.strip()
    if content.startswith("```json"): content = content[7:-3]
    elif content.startswith("```"): content = content[3:-3]
    return json.loads(content)

def evaluate_retrieved_chunks(question: str, ground_truth: str, chunks: List[str]) -> Dict[str, float]:
    context = "\n\n".join([f"Chunk {i+1}:\n{c}" for i, c in enumerate(chunks)])
    
    # 1. Evaluate Precision (Is the context relevant?)
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
        
    # 2. Evaluate Recall (Does the context contain ENOUGH information to answer?)
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
    parser.add_argument("--file", required=True, help="Tên file markdown trong thư mục data/knowledge_base/processed/")
    args = parser.parse_args()
    
    base_dir = Path("data/knowledge_base/processed")
    file_path = base_dir / args.file
    if not file_path.exists():
        if (base_dir / f"{args.file}.md").exists():
            file_path = base_dir / f"{args.file}.md"
        else:
            print(f"File {file_path} không tồn tại.")
            sys.exit(1)
            
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()
        
    gold_qa_file = Path("evaluate/gold_qa") / f"{Path(args.file).stem}_gold_qa.json"
    if gold_qa_file.exists():
        print(f"Sử dụng bộ Gold QA có sẵn: {gold_qa_file.name}")
        with open(gold_qa_file, "r", encoding="utf-8") as f:
            qa_pairs = json.load(f)
    else:
        # Generate Ground Truth
        qa_pairs = generate_ground_truth(text, num_questions=5)
        
    print(f"Đã nạp {len(qa_pairs)} câu hỏi đánh giá.")
    
    methods = {
        "Parent Document Chunking": ParentDocumentChunker(),
        "Semantic Chunking": SemanticDocumentChunker(),
        "Advanced LLM Chunking": AdvancedLLMChunker()
    }
    
    embeddings = HuggingFaceEmbeddings(
        model_name=settings.huggingface_embedding_model,
        model_kwargs={'device': 'cpu'}, 
        encode_kwargs={'normalize_embeddings': True}
    )
    
    results = {}
    
    for name, chunker in methods.items():
        print(f"\n--- Đang đánh giá {name} ---")
        
        # 1. Chunking
        import time
        start_time = time.time()
        docs = chunker.chunk(text, source=args.file)
        chunking_time = time.time() - start_time
        
        print(f"Tạo được {len(docs)} chunks trong {chunking_time:.2f}s")
        
        if not docs:
            print("Không sinh ra được chunk nào!")
            results[name] = {"Chunks": 0, "Avg Chunk Length": 0, "Time (s)": round(chunking_time, 2), "Precision": 0, "Recall": 0}
            continue
            
        # 2. Embed into FAISS
        vectorstore = FAISS.from_documents(docs, embeddings)
        retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
        
        # 3. Evaluate
        total_precision = 0
        total_recall = 0
        for qa in qa_pairs:
            q = qa['question']
            a = qa['answer']
            retrieved_docs = retriever.invoke(q)
            retrieved_texts = [d.page_content for d in retrieved_docs]
            
            scores = evaluate_retrieved_chunks(q, a, retrieved_texts)
            total_precision += scores['precision']
            total_recall += scores['recall']
            
        avg_precision = total_precision / len(qa_pairs) if qa_pairs else 0
        avg_recall = total_recall / len(qa_pairs) if qa_pairs else 0
        
        results[name] = {
            "Chunks": len(docs),
            "Avg Chunk Length": sum(len(d.page_content) for d in docs) / len(docs) if docs else 0,
            "Time (s)": round(chunking_time, 2),
            "Precision": round(avg_precision * 100, 2),
            "Recall": round(avg_recall * 100, 2)
        }
        
    # Write Report
    report_lines = [
        "# Báo cáo đánh giá Chunking Methods",
        f"**File test:** {args.file}",
        f"**Số lượng câu hỏi (Ground Truth):** {len(qa_pairs)}",
        "",
        "| Phương pháp | Tổng Chunks | Kích thước TB (ký tự) | Thời gian (s) | Precision (%) | Recall (%) |",
        "|-------------|-------------|-----------------------|---------------|---------------|------------|"
    ]
    
    for name, data in results.items():
        report_lines.append(
            f"| {name} | {data['Chunks']} | {data['Avg Chunk Length']:.0f} | {data['Time (s)']} | **{data['Precision']}%** | **{data['Recall']}%** |"
        )
        
    report_content = "\n".join(report_lines)
    report_path = Path("evaluate/results/chunking/chunking_evaluation_report.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)
        
    print(f"\n✅ Đã xuất báo cáo tại: {report_path.resolve()}")

if __name__ == "__main__":
    main()
