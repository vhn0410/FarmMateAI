import os
import sys
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv

from unittest.mock import MagicMock

# =====================================================================
# MONKEY PATCH: Sửa lỗi xung đột Langchain v0.3 và RAGAS
# BẮT BUỘC ĐỂ TRÊN CÙNG
# =====================================================================
sys.modules["langchain_community.chat_models.vertexai"] = MagicMock()
sys.modules["langchain_community.llms.vertexai"] = MagicMock()


load_dotenv()


def run_cron_evaluation():
    from datasets import Dataset
    from ragas import evaluate
    from ragas.metrics import (
        faithfulness,
        answer_relevancy,
        context_precision,
        context_recall,
    )
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    from ragas.llms import LangchainLLMWrapper
    from ragas.embeddings import LangchainEmbeddingsWrapper

    # Thêm root path để import từ thư mục app
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.append(backend_dir)

    from app.infrastructure.llm.openai_client import OpenAIClient
    from app.infrastructure.vector_store.pgvector_provider import PGVectorProvider
    from app.infrastructure.external.google_drive import GoogleDriveProvider
    from app.agents.skills.rag_agriculture.tool import AgricultureRAGSkill

    print("🚀 BẮT ĐẦU CRONJOB ĐÁNH GIÁ RAGAS...")

    # 1. Khởi tạo các thành phần
    llm_provider = OpenAIClient(model="gpt-4o-mini", temperature=0.0)
    vector_store = PGVectorProvider()
    rag_skill = AgricultureRAGSkill(
        vector_store_provider=vector_store, llm_provider=llm_provider
    )
    drive_provider = GoogleDriveProvider()

    print("\n☁️ Đang tìm và tải 'ground_truth.json' từ Google Drive...")
    # Chú ý: Đảm bảo bạn đã export DRIVE_GROUND_TRUTH_FOLDER_ID trong file .env
    folder_id = os.getenv("DRIVE_GROUND_TRUTH_FOLDER_ID")

    file_id = drive_provider.get_file_id_by_name("ground_truth.json", folder_id)
    if not file_id:
        print(
            "❌ LỖI: Không tìm thấy file 'ground_truth.json' trong thư mục Drive chỉ định!"
        )
        return  # Dừng toàn bộ chương trình nếu không có data

    ground_truths = drive_provider.download_json(file_id)

    if not ground_truths:
        print("❌ LỖI: Không thể đọc dữ liệu JSON từ file!")
        return

    print(f"✅ Đã tải xong {len(ground_truths)} câu hỏi thử nghiệm từ Drive.")

    results = []

    # =================================================================
    # PHASE 1: CHẠY THỬ NGHIỆM ĐỂ LẤY KẾT QUẢ VÀ CONTEXTS
    # =================================================================
    for idx, item in enumerate(ground_truths):
        question = item["question"]
        expected_answer = item["ground_truth_answer"]

        print(
            f"\n[{idx + 1}/{len(ground_truths)}] Sinh câu trả lời cho: {question[:50]}..."
        )
        skill_result = rag_skill.run(query=question)

        contexts = []
        if skill_result.metadata and "sources" in skill_result.metadata:
            for source in skill_result.metadata["sources"]:
                # Đảm bảo dùng full_content thay vì snippet để RAGAS chấm chính xác
                contexts.append(source.get("full_content", ""))

        results.append(
            {
                "question": question,
                "ground_truth": expected_answer,
                "answer": skill_result.answer,
                "contexts": contexts,
            }
        )

    # =================================================================
    # PHASE 2: CHẤM ĐIỂM RAGAS
    # =================================================================
    print("\n⚖️ BẮT ĐẦU CHẤM ĐIỂM RAGAS...")
    df = pd.DataFrame(results)
    dataset = Dataset.from_pandas(df)

    from langchain_huggingface import HuggingFaceEmbeddings
    from app.core.config import settings

    chat_kwargs = {"model": "gpt-4o-mini", "temperature": 0.0}
    if settings.openai_api_base:
        chat_kwargs["base_url"] = settings.openai_api_base

    judge_llm = LangchainLLMWrapper(ChatOpenAI(**chat_kwargs))
    judge_embeddings = LangchainEmbeddingsWrapper(
        HuggingFaceEmbeddings(
            model_name=settings.huggingface_embedding_model,
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )
    )
    metrics = [context_precision, context_recall, faithfulness, answer_relevancy]

    eval_result = evaluate(
        dataset=dataset,
        metrics=metrics,
        llm=judge_llm,
        embeddings=judge_embeddings,
    )

    print("\n📊 TỔNG KẾT ĐIỂM:")
    print(eval_result)

    # =================================================================
    # PHASE 3: XUẤT FILE CÓ TIMESTAMP VÀ LƯU VĨNH VIỄN Ở LOCAL
    # =================================================================
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Đặt tên file động
    raw_filename = f"raw_results_{timestamp}.csv"
    final_filename = f"ragas_scores_{timestamp}.csv"

    # Thay vì lưu thư mục temp, ta lưu thẳng vào thư mục evaluations/results
    results_dir = os.path.join(backend_dir, "scripts", "temp", "evaluations", "results")
    os.makedirs(results_dir, exist_ok=True)

    raw_local_path = os.path.join(results_dir, raw_filename)
    final_local_path = os.path.join(results_dir, final_filename)

    # Lưu ra máy
    df.to_csv(raw_local_path, index=False, encoding="utf-8-sig")
    eval_result.to_pandas().to_csv(final_local_path, index=False, encoding="utf-8-sig")

    print("\n📁 Đã lưu báo cáo đánh giá thành công tại Local:")
    print(f" 📄 Kết quả thô: {raw_local_path}")
    print(f" 📊 Bảng điểm RAGAS: {final_local_path}")
    print("✅ Hoàn tất chu trình Cronjob!")


if __name__ == "__main__":
    run_cron_evaluation()
