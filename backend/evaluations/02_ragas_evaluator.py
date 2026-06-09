import os
import ast
import sys
from unittest.mock import MagicMock
import pandas as pd
from dotenv import load_dotenv

from datasets import Dataset

# =====================================================================
# HACK / MONKEY PATCH ĐỂ FIX LỖI XUNG ĐỘT LANGCHAIN v0.3+ VÀ RAGAS
# RAGAS bị crash lúc import vì tìm module cũ của Google.
# Ta tạo một module "giả" nhét vào hệ thống để lừa RAGAS bỏ qua lỗi này.
# =====================================================================
sys.modules["langchain_community.chat_models.vertexai"] = MagicMock()
sys.modules["langchain_community.llms.vertexai"] = MagicMock()
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

load_dotenv()


def run_ragas_evaluation():
    print("⚖️ BẮT ĐẦU CHẤM ĐIỂM BẰNG RAGAS...")

    # 1. Load file kết quả thô
    input_path = "evaluations/results/raw_experiment_results.csv"
    if not os.path.exists(input_path):
        print(
            f"❌ Lỗi: Không tìm thấy file {input_path}. Hãy chạy 01_run_experiments.py trước."
        )
        return

    df = pd.DataFrame(pd.read_csv(input_path))

    # Sửa lỗi parse list
    df["contexts"] = df["contexts"].apply(ast.literal_eval)

    # 2. Chuyển đổi Pandas DataFrame sang HuggingFace Dataset
    dataset = Dataset.from_pandas(df)

    # 3. Khởi tạo Giám khảo LLM (Judge) và bọc lại bằng Wrapper
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0)
    judge_llm = LangchainLLMWrapper(llm)

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    judge_embeddings = LangchainEmbeddingsWrapper(embeddings)

    # 4. Định nghĩa các độ đo (Metrics)
    metrics = [
        context_precision,
        context_recall,
        faithfulness,
        answer_relevancy,
    ]

    print(
        f"🔄 Đang gửi {len(dataset)} câu hỏi cho Giám khảo LLM chấm điểm. Vui lòng chờ vài phút..."
    )

    # 5. Thực thi đánh giá
    result = evaluate(
        dataset=dataset,
        metrics=metrics,
        llm=judge_llm,
        embeddings=judge_embeddings,
    )

    # 6. In và Lưu kết quả
    print("\n" + "=" * 50)
    print("📊 TỔNG KẾT ĐIỂM RAGAS (0.0 -> 1.0)")
    print("=" * 50)
    print(result)

    result_df = result.to_pandas()
    output_path = "evaluations/results/ragas_final_scores.csv"
    result_df.to_csv(output_path, index=False, encoding="utf-8-sig")

    print(f"\n📁 Đã lưu bảng điểm chi tiết tại: {output_path}")


if __name__ == "__main__":
    run_ragas_evaluation()
