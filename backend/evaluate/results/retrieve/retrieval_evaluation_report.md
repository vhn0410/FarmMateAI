# Báo cáo Đánh giá Retrieval Methods
**File test:** so-tay-huong-dan-quy-trinh-1-trieu-ha-dbscl-ngay-27-3-2024.md
**Số lượng câu hỏi (Gold QA):** 20
**Chunking Method Base:** Parent Document Chunking
**Top K Retrieve:** 3

| Phương pháp Truy xuất | Thời gian đánh giá (s) | Precision (%) | Recall (%) |
|-----------------------|------------------------|---------------|------------|
| Pure Vector Search (FAISS) | 77.16 | **87.5%** | **62.5%** |
| Pure Keyword Search (BM25) | 76.69 | **90.0%** | **82.5%** |
| Hybrid Search (RRF 50/50) | 75.35 | **97.5%** | **77.5%** |
| Production Hybrid + Reranker | 134.72 | **100.0%** | **95.0%** |