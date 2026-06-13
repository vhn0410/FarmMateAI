import pandas as pd


def calculate_average_metrics(file_path):
    # Đọc file dữ liệu
    df = pd.read_csv(file_path)

    # Xác định các cột chứa metrics đánh giá (Ragas metrics)
    metrics_cols = [
        "context_precision",
        "context_recall",
        "faithfulness",
        "answer_relevancy",
    ]

    # Tính giá trị trung bình cho các cột này
    # skipna=True để bỏ qua các giá trị rỗng (NaN) nếu có trong quá trình tính toán
    averages = df[metrics_cols].mean(skipna=True)

    print("Điểm trung bình của các Ragas Metrics:")
    print("-" * 40)
    for metric, value in averages.items():
        print(f"{metric:<20}: {value:.4f}")


# Gọi hàm với tên file của bạn
if __name__ == "__main__":
    file_name = "./results/ragas_scores_20260612_204623.csv"
    calculate_average_metrics(file_name)
