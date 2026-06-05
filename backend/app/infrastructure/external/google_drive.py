import os
from pathlib import Path
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# from langchain_google_community import GoogleDriveLoader
from langchain_community.document_loaders import GoogleDriveLoader
from dotenv import load_dotenv
from langchain_core.documents import Document

# Import Interface từ tầng Domain
from app.domain.interfaces.document_provider import IDocumentProvider

# Load các ID từ file .env
load_dotenv()
DRIVE_NEW_FOLDER_ID = os.getenv("DRIVE_NEW_FOLDER_ID")
DRIVE_PROCESSED_FOLDER_ID = os.getenv("DRIVE_PROCESSED_FOLDER_ID")

# Resolve credentials.json từ backend root directory (tự động, không phụ thuộc cwd)
_backend_dir = Path(__file__).resolve().parents[3]  # Up 3 levels: external/ -> infrastructure/ -> app/ -> backend/
_creds_env = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")

# Nếu là relative path, resolve từ backend root; nếu là absolute path, dùng nguyên
if Path(_creds_env).is_absolute():
    CREDENTIALS_PATH = _creds_env
else:
    CREDENTIALS_PATH = str(_backend_dir / _creds_env)


class MemoryTextLoader:
    """Reads in-memory file objects downloaded from Google Drive."""

    def __init__(self, file, **kwargs):
        self.file = file

    def load(self):
        # Decode the raw bytes into a readable string
        content = self.file.read().decode("utf-8")
        return [Document(page_content=content)]


class GoogleDriveProvider(IDocumentProvider):
    """Class thực thi (Implementation) chi tiết cho Google Drive"""

    def __init__(self):
        self.service = self._get_drive_service()

    def _get_drive_service(self):
        """Khởi tạo Google Drive API Client."""
        # Check if credentials file exists
        if not Path(CREDENTIALS_PATH).exists():
            raise FileNotFoundError(
                f"Credentials file not found at: {CREDENTIALS_PATH}\n"
                f"Please ensure credentials.json exists in the backend root directory."
            )
        
        scopes = ["https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_file(CREDENTIALS_PATH, scopes=scopes)
        service = build("drive", "v3", credentials=creds)
        return service

    def fetch_new_documents(self) -> list:
        """Đọc tài liệu dạng markdown từ thư mục NEW."""
        loader = GoogleDriveLoader(
            folder_id=DRIVE_NEW_FOLDER_ID,
            recursive=False,
            file_loader_cls=MemoryTextLoader,
            service_account_key=CREDENTIALS_PATH,
        )
        return loader.load()

    def mark_as_processed(self, file_id: str):
        """
        Di chuyển file từ thư mục NEW sang thư mục PROCESSED.
        """
        try:
            # Drive API yêu cầu thao tác thêm/xóa parent
            self.service.files().update(
                fileId=file_id,
                addParents=DRIVE_PROCESSED_FOLDER_ID,
                removeParents=DRIVE_NEW_FOLDER_ID,
                fields="id, parents",
            ).execute()

            print(f" Đã chuyển file {file_id} sang thư mục Processed.")
        except Exception as e:
            print(f" Lỗi khi chuyển file {file_id}: {str(e)}")
