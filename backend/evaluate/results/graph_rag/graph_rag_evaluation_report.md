# Báo cáo Đánh giá Graph RAG so với Standard RAG
**File test:** so-tay-huong-dan-quy-trinh-1-trieu-ha-dbscl-ngay-27-3-2024.md
**Số lượng câu hỏi (Gold QA):** 5
**Top K Retrieve (Vector):** 3

| Phương pháp Truy xuất | Thời gian đánh giá (s) | Precision (%) | Recall (%) |
|-----------------------|------------------------|---------------|------------|
| Baseline: Pure Vector RAG | 34.9 | **80.0%** | **60.0%** |
| Pure Graph RAG | 42.15 | **0.0%** | **0.0%** |
| Parallel Graph + Vector RAG | 38.44 | **100.0%** | **80.0%** |