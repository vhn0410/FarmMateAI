import os
import logging
from sqlalchemy import text
from alembic import command
from alembic.config import Config
from app.infrastructure.db.session import engine
from app.infrastructure.vector_store.pgvector_provider import PGVectorProvider

logger = logging.getLogger(__name__)

def initialize_database():
    """
    Tự động hóa quá trình set up schema cho cơ sở dữ liệu:
    1. Chạy Alembic Migrations để tạo/cập nhật các bảng như users, conversations, messages.
    2. Đảm bảo Extension pgvector được tạo.
    3. Tạo bảng langchain_pg_embedding (thông qua PGVector).
    4. Thêm cột fts_vector và đánh index GIN cho Full-Text Search.
    5. Tạo bảng langchain_pg_docstore cho Parent Document Chunking.
    """
    logger.info("Bắt đầu khởi tạo Database tự động...")
    
    # Lấy thư mục gốc của backend (nơi chứa file alembic.ini)
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    alembic_ini_path = os.path.join(backend_dir, "alembic.ini")
    
    # 1. Chạy Alembic Upgrade
    try:
        if os.path.exists(alembic_ini_path):
            alembic_cfg = Config(alembic_ini_path)
            # Chuyển context sang thư mục chứa alembic.ini để alembic có thể tìm thấy thư mục versions
            original_dir = os.getcwd()
            os.chdir(backend_dir)
            command.upgrade(alembic_cfg, "head")
            os.chdir(original_dir)
            logger.info("Đã chạy Alembic migrations thành công.")
        else:
            logger.warning(f"Không tìm thấy file alembic.ini tại {alembic_ini_path}")
    except Exception as e:
        logger.error(f"Lỗi khi chạy Alembic migrations: {e}")
        # Không throw error để DB vẫn tiếp tục khởi tạo các bảng khác
        
    # 2. & 3. Khởi tạo PGVector (sẽ tự động tạo bảng langchain_pg_embedding nếu chưa có)
    # Khởi tạo instance provider (sẽ tải HuggingFaceEmbeddings và gọi PGVector.__init__ có chứa create_tables_if_not_exists)
    try:
        provider = PGVectorProvider()
        # Đảm bảo connection đã tạo bảng
        logger.info("Đã khởi tạo bảng Vector thông qua PGVectorProvider.")
    except Exception as e:
        logger.error(f"Lỗi khi khởi tạo PGVector: {e}")

    # 4. Thêm cột fts_vector và Index cho Full Text Search
    try:
        with engine.begin() as conn:
            # Thêm cột
            conn.execute(text("""
                ALTER TABLE public.langchain_pg_embedding 
                ADD COLUMN IF NOT EXISTS fts_vector tsvector 
                GENERATED ALWAYS AS (to_tsvector('simple', document)) STORED;
            """))
            # Đánh Index
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_fts_search 
                ON public.langchain_pg_embedding USING GIN (fts_vector);
            """))
            logger.info("Đã cấu hình Full-Text Search cho bảng langchain_pg_embedding.")
    except Exception as e:
        logger.error(f"Lỗi khi thêm cột fts_vector: {e}")

    # 5. Khởi tạo bảng langchain_pg_docstore cho Parent Document Retriever
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS public.langchain_pg_docstore (
                    id character varying NOT NULL,
                    document jsonb NOT NULL,
                    CONSTRAINT langchain_pg_docstore_pkey PRIMARY KEY (id)
                );
            """))
            logger.info("Đã tạo bảng langchain_pg_docstore.")
    except Exception as e:
        logger.error(f"Lỗi khi tạo bảng langchain_pg_docstore: {e}")
        
    logger.info("Khởi tạo Database hoàn tất!")

if __name__ == "__main__":
    initialize_database()
