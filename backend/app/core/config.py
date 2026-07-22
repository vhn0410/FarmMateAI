from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM Configuration
    openai_api_key: str
    openai_api_base: str | None = None
    huggingface_embedding_model: str = "keepitreal/vietnamese-sbert"
    llama_cloud_api_key: str | None = None

    # Database Configuration
    postgres_connection_string: str
    collection_name: str = "enterprise_rag_documents"

    # Google Drive Configuration
    drive_new_folder_id: str
    drive_processed_folder_id: str
    google_credentials_path: str = "credentials.json"
    drive_ground_truth_folder_id: str
    openweathermap_base_url: str
    openweathermap_api_key: str
    # Authentication setting
    auth_mode: str
    # Keycloak
    keycloak_url: str
    # THÊM DÒNG NÀY VÀO:
    jwt_secret_key: str = "123456"

    # Neo4j Graph Configuration
    neo4j_uri: str = "bolt://neo4j:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = "farmmatepassword"

    # Storage Configuration
    storage_provider: str = "local" # "local" or "s3"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_region: str | None = None
    aws_bucket_name: str | None = None

    # Application Settings
    environment: str = "development"
    debug: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Single instance - load once
settings = Settings()
