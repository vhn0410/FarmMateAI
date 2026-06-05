import os
from langchain_openai import OpenAIEmbeddings
from langchain_postgres import PGVector
from dotenv import load_dotenv

load_dotenv()
# Đọc từ biến môi trường (cấu hình trong file .env)
DB_CONNECTION = os.getenv(
    "POSTGRES_CONNECTION_STRING", "postgresql+psycopg2://user:pass@localhost:5432/db"
)
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "enterprise_rag_documents")


def get_embeddings_model():
    return OpenAIEmbeddings(model="text-embedding-3-small")


def get_vector_store() -> PGVector:
    """Khởi tạo và trả về instance của PGVector."""
    return PGVector(
        embeddings=get_embeddings_model(),
        collection_name=COLLECTION_NAME,
        connection=DB_CONNECTION,
        use_jsonb=True,  # Tối ưu lưu trữ metadata (chunk_id, hierarchy...)
    )
