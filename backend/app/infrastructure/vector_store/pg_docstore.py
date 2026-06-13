import json
from typing import List, Optional, Sequence, Tuple
from sqlalchemy import text
from sqlalchemy.engine import Engine
from langchain_core.stores import BaseStore
from langchain_core.documents import Document


class PostgresDocStore(BaseStore[str, Document]):
    """
    Adapter giúp Langchain ParentDocumentRetriever nói chuyện được với bảng Postgres.
    """

    def __init__(self, engine: Engine):
        self.engine = engine

    def mget(self, keys: Sequence[str]) -> List[Optional[Document]]:
        """Lấy danh sách Parent Documents bằng ID."""
        with self.engine.connect() as conn:
            query = text(
                "SELECT id, document FROM public.langchain_pg_docstore WHERE id = ANY(:keys)"
            )
            result = conn.execute(query, {"keys": list(keys)}).fetchall()

            # Map kết quả trả về đúng thứ tự keys
            doc_dict = {}
            for row in result:
                doc_data = row.document
                doc_dict[row.id] = Document(
                    page_content=doc_data.get("page_content", ""),
                    metadata=doc_data.get("metadata", {}),
                )
            return [doc_dict.get(k) for k in keys]

    def mset(self, key_value_pairs: Sequence[Tuple[str, Document]]) -> None:
        """Lưu Parent Documents vào bảng."""
        with self.engine.begin() as conn:  # Tự động commit
            query = text("""
                INSERT INTO public.langchain_pg_docstore (id, document) 
                VALUES (:id, :document)
                ON CONFLICT (id) DO UPDATE SET document = EXCLUDED.document
            """)

            params = [
                {
                    "id": k,
                    "document": json.dumps(
                        {"page_content": v.page_content, "metadata": v.metadata}
                    ),
                }
                for k, v in key_value_pairs
            ]
            conn.execute(query, params)

    def mdelete(self, keys: Sequence[str]) -> None:
        """Xóa Parent Documents (dùng cho tính năng Update/Sync)."""
        with self.engine.begin() as conn:
            query = text(
                "DELETE FROM public.langchain_pg_docstore WHERE id = ANY(:keys)"
            )
            conn.execute(query, {"keys": list(keys)})

    def yield_keys(self, prefix: Optional[str] = None):
        raise NotImplementedError("Không cần thiết cho ParentDocumentRetriever")
