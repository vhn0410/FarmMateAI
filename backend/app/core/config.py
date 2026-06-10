from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM Configuration
    openai_api_key: str

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
    # Application Settings
    environment: str = "development"
    debug: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Single instance - load once
settings = Settings()
