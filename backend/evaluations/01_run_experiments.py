import os
import json
import sys
import time
import pandas as pd
from dotenv import load_dotenv
# Thêm root path để import được thư mục app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Import các components từ Core/Infra của dự án chính
from app.infrastructure.llm.openai_client import OpenAIClient
from app.infrastructure.vector_store.pgvector_provider import PGVectorProvider
from app.agents.skills.rag_agriculture.tool import AgricultureRAGSkill

load_dotenv()

def run_evaluation_experiment():
    print("🚀 BẮT ĐẦU CHẠY THỬ NGHIỆM ĐÁNH GIÁ HỆ THỐNG RAG...")
    
    # 1. Khởi tạo RAG System thật (giống hệt lúc chạy Production)
    llm_provider = OpenAIClient(model="gpt-4o-mini", temperature=0.0)
    vector_store = PGVectorProvider()
    rag_skill = AgricultureRAGSkill(
        vector_store_provider=vector_store,
        llm_provider=llm_provider
    )

    # 2. Đọc bộ câu hỏi Ground Truth
    dataset_path = "evaluations/dataset/ground_truth.json"
    with open(dataset_path, 'r', encoding='utf-8') as f:
        ground_truths = json.load(f)

    results = []

    # 3. Vòng lặp bắn từng câu hỏi vào hệ thống
    for idx, item in enumerate(ground_truths):
        question = item['question']
        expected_answer = item['ground_truth_answer']
        
        print(f"\n[{idx+1}/{len(ground_truths)}] Đang xử lý câu hỏi: {question[:50]}...")
        start_time = time.time()
        
        # GỌI HỆ THỐNG THẬT LÀM VIỆC
        skill_result = rag_skill.run(query=question)
        
        # Bóc tách dữ liệu chuẩn bị cho RAGAS
        actual_answer = skill_result.answer
        
        # RAGAS yêu cầu contexts là một List[str]
        contexts = []
        if skill_result.metadata and "sources" in skill_result.metadata:
            # Lấy nguyên văn content từ các tài liệu tìm được
            for source in skill_result.metadata["sources"]:
                contexts.append(source.get("full_content", ""))
                
        execution_time = time.time() - start_time
        
        print(f"  ✅ Trả lời xong. TG: {execution_time:.2f}s | Tìm thấy {len(contexts)} chunks.")

        # Lưu lại bản ghi
        results.append({
            "question": question,
            "ground_truth": expected_answer,
            "answer": actual_answer,
            "contexts": contexts, # CỰC KỲ QUAN TRỌNG CHO RAGAS
        })

    # 4. Lưu kết quả thô ra file CSV (hoặc JSON)
    df = pd.DataFrame(results)
    
    # Đảm bảo thư mục results tồn tại
    os.makedirs("evaluations/results", exist_ok=True)
    
    output_path = "evaluations/results/raw_experiment_results.csv"
    df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"\n🎉 Đã lưu kết quả thô thành công tại: {output_path}")

if __name__ == "__main__":
    run_evaluation_experiment()