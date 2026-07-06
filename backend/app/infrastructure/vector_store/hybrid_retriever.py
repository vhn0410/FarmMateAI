from typing import List, Any
from langchain_core.retrievers import BaseRetriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from sqlalchemy import text
from app.infrastructure.db.session import engine
import json
import re
from langchain_classic.retrievers.parent_document_retriever import ParentDocumentRetriever


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

        # 1.5. Chuyển đổi câu hỏi thành dạng OR cho Full-Text Search
        # FTS websearch mặc định là AND, nếu dùng cho câu hỏi tự nhiên sẽ không tìm thấy gì nếu thiếu 1 chữ
        clean_query = re.sub(r'[^\w\s]', '', query)
        fts_query = " OR ".join([w for w in clean_query.split() if w.strip()])
        if not fts_query:
            fts_query = query # Fallback

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
                       RANK() OVER (ORDER BY ts_rank_cd(fts_vector, websearch_to_tsquery('simple', :fts_query)) DESC) AS rank,
                       ts_headline('simple', document, websearch_to_tsquery('simple', :fts_query), 'StartSel=<b>, StopSel=</b>, MaxWords=35, MinWords=15') AS match_keywords
                FROM langchain_pg_embedding
                WHERE fts_vector @@ websearch_to_tsquery('simple', :fts_query)
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
        docs = []

        try:
            with engine.connect() as conn:
                result = conn.execute(
                    text(sql),
                    {
                        "query": query,
                        "fts_query": fts_query,
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

class HybridParentDocumentRetriever(ParentDocumentRetriever):
    """
    Kế thừa ParentDocumentRetriever nhưng ghi đè `_get_relevant_documents` 
    để sử dụng Hybrid Search lấy Child Chunks, sau đó map lên Parent Document.
    """
    connection_string: str
    embeddings: Any
    top_k: int = 5
    
    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> List[Document]:
        
        # 1. Trích xuất filter logic từ search_kwargs (nếu có)
        filter_clause = ""
        valid_ids = []
        if self.search_kwargs and "filter" in self.search_kwargs:
            f = self.search_kwargs["filter"]
            if "file_id" in f and "$in" in f["file_id"]:
                valid_ids = f["file_id"]["$in"]
                if valid_ids:
                    # Chuyển list Python thành chuỗi JSON mảng để SQL dễ xử lý
                    valid_ids_json = json.dumps(valid_ids)
                    filter_clause = "AND cmetadata->>'file_id' IN (SELECT json_array_elements_text(CAST(:valid_ids AS json)))"
        
        query_embedding = self.embeddings.embed_query(query)
        query_embedding_str = str(query_embedding)

        clean_query = re.sub(r'[^\w\s]', '', query)
        fts_query = " OR ".join([w for w in clean_query.split() if w.strip()])
        if not fts_query:
            fts_query = query

        sql = f"""
            WITH vector_search AS (
                SELECT id, document, cmetadata,
                       RANK() OVER (ORDER BY embedding <=> CAST(:embedding AS vector)) AS rank
                FROM langchain_pg_embedding
                WHERE 1=1 {filter_clause}
                LIMIT 50
            ),
            keyword_search AS (
                SELECT id, document, cmetadata,
                       RANK() OVER (ORDER BY ts_rank_cd(fts_vector, websearch_to_tsquery('simple', :fts_query)) DESC) AS rank,
                       ts_headline('simple', document, websearch_to_tsquery('simple', :fts_query), 'StartSel=<b>, StopSel=</b>, MaxWords=35, MinWords=15') AS match_keywords
                FROM langchain_pg_embedding
                WHERE fts_vector @@ websearch_to_tsquery('simple', :fts_query)
                {filter_clause}
                LIMIT 50
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
            LIMIT 50
        """

        child_docs = []
        
        try:
            with engine.connect() as conn:
                params = {
                    "query": query,
                    "fts_query": fts_query,
                    "embedding": query_embedding_str,
                }
                if valid_ids:
                    params["valid_ids"] = valid_ids_json
                    
                result = conn.execute(text(sql), params)

                for row in result:
                    metadata = row.cmetadata if row.cmetadata else {}
                    metadata["hybrid_rrf_score"] = float(row.rrf_score)
                    metadata["vector_rank"] = row.vector_rank
                    metadata["keyword_rank"] = row.keyword_rank
                    if row.highlighted_text:
                        metadata["fts_highlight"] = row.highlighted_text
                    child_docs.append(Document(page_content=row.document, metadata=metadata))
                    
        except Exception as e:
            print(f"[HybridParentDocumentRetriever Lỗi SQL]: {e}")
            return []

        # Lọc ra danh sách doc_id (Parent ID)
        parent_ids = []
        best_child_meta = {}
        
        for doc in child_docs:
            doc_id = doc.metadata.get(self.id_key)
            if doc_id:
                if doc_id not in parent_ids:
                    parent_ids.append(doc_id)
                    best_child_meta[doc_id] = doc.metadata # Giữ metadata của chunk tốt nhất
        
        # Load Parent Documents
        parent_docs_result = self.docstore.mget(parent_ids)
        parent_docs = []
        
        print(f"\n🚀 [HYBRID PARENT SEARCH RUNNING] 🚀")
        print(f"👉 Câu hỏi: {query}")
        
        for i, p_doc in enumerate(parent_docs_result):
            if p_doc is not None:
                p_id = parent_ids[i]
                meta = best_child_meta[p_id]
                
                # Gắn Hybrid Meta vào Parent
                p_doc.metadata.update({
                    "hybrid_rrf_score": meta.get("hybrid_rrf_score"),
                    "vector_rank": meta.get("vector_rank"),
                    "keyword_rank": meta.get("keyword_rank"),
                    "fts_highlight": meta.get("fts_highlight"),
                })
                parent_docs.append(p_doc)
                
                print(f"--- Parent Doc: {p_doc.metadata.get('file_id', p_id)} | RRF: {meta.get('hybrid_rrf_score'):.4f} ---")
                if meta.get("fts_highlight"):
                    print(f"  > 🔍 Keyword Match: {meta.get('fts_highlight')}")
                else:
                    print("  > 🤖 Chỉ tìm thấy bằng Vector Semantics (Ngữ nghĩa)")

        print("-" * 50 + "\n")
        
        # Trả về theo thứ tự đã sort RRF của child_docs (mget bảo toàn thứ tự parent_ids)
        # Giới hạn top_k parent docs
        return parent_docs[:self.top_k]

