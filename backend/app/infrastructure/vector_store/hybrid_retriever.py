from typing import List, Any
from langchain_core.retrievers import BaseRetriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from sqlalchemy import create_engine, text


class PostgresHybridRetriever(BaseRetriever):
    """
    Custom Retriever thực hiện Hybrid Search trực tiếp dưới PostgreSQL.
    Sử dụng thuật toán Reciprocal Rank Fusion (RRF) để gộp điểm Vector và Keyword.
    """

    connection_string: str
    embeddings: Any
    top_k: int = 5

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> List[Document]:

        # 1. Biến câu hỏi của user thành Vector
        query_embedding = self.embeddings.embed_query(query)
        query_embedding_str = str(query_embedding)  # Ép kiểu chuỗi để truyền vào SQL

        # 2. Câu SQL thực hiện Hybrid Search (Vector + FTS)
        sql = """
            WITH vector_search AS (
                SELECT id, document, cmetadata,
                       RANK() OVER (ORDER BY embedding <=> CAST(:embedding AS vector)) AS rank
                FROM langchain_pg_embedding
                LIMIT 20
            ),
            keyword_search AS (
                SELECT id, document, cmetadata,
                       -- Dùng websearch_to_tsquery để search linh hoạt hơn với câu dài
                       RANK() OVER (ORDER BY ts_rank_cd(fts_vector, websearch_to_tsquery('simple', :query)) DESC) AS rank,
                       ts_headline('simple', document, websearch_to_tsquery('simple', :query), 'StartSel=<b>, StopSel=</b>, MaxWords=35, MinWords=15') AS match_keywords
                FROM langchain_pg_embedding
                WHERE fts_vector @@ websearch_to_tsquery('simple', :query)
                LIMIT 20
            )
            SELECT
                COALESCE(v.id, k.id) as id,
                COALESCE(v.document, k.document) as document,
                COALESCE(v.cmetadata, k.cmetadata) as cmetadata,
                (COALESCE(1.0 / (60 + v.rank), 0.0) + COALESCE(1.0 / (60 + k.rank), 0.0)) as rrf_score,
                v.rank as vector_rank,
                k.rank as keyword_rank,
                k.match_keywords as highlighted_text
            FROM vector_search v
            FULL OUTER JOIN keyword_search k ON v.id = k.id
            ORDER BY rrf_score DESC
            LIMIT :top_k
        """
        # 3. Kết nối DB và thực thi
        engine = create_engine(self.connection_string, echo=True)
        docs = []

        try:
            with engine.connect() as conn:
                result = conn.execute(
                    text(sql),
                    {
                        "query": query,
                        "embedding": query_embedding_str,
                        "top_k": self.top_k,
                    },
                )

                # 4. Đóng gói kết quả thành chuẩn Document của LangChain
                for row in result:
                    metadata = row.cmetadata if row.cmetadata else {}

                    # Gắn RRF Score
                    metadata["hybrid_rrf_score"] = float(row.rrf_score)

                    # === ĐÃ BỔ SUNG: Gắn Rank và Highlight từ SQL row vào Python ===
                    metadata["vector_rank"] = row.vector_rank
                    metadata["keyword_rank"] = row.keyword_rank

                    if row.highlighted_text:
                        metadata["fts_highlight"] = row.highlighted_text

                    docs.append(Document(page_content=row.document, metadata=metadata))
            # --- LOG CHI TIẾT ĐỂ BẠN THẤY TỪ KHÓA ---
            print("\n🚀 [HYBRID SEARCH RUNNING]")
            print(f"👉 Câu hỏi: {query}")
            for i, doc in enumerate(docs):
                print(
                    f"--- Top {i + 1} | Điểm RRF: {doc.metadata.get('hybrid_rrf_score'):.4f} ---"
                )
                print(
                    f"  > Hạng Vector: {doc.metadata.get('vector_rank')} | Hạng Keyword: {doc.metadata.get('keyword_rank')}"
                )
                if "fts_highlight" in doc.metadata:
                    print(f"  > 🔍 Keyword Match: {doc.metadata['fts_highlight']}")
                else:
                    print("  > 🤖 Chỉ tìm thấy bằng Vector Semantics (Ngữ nghĩa)")
            print("-" * 40 + "\n")
        except Exception as e:
            print(f"[Hybrid Retriever Lỗi]: {e}")

        return docs
