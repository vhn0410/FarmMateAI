import os
import json
import io
from pathlib import Path
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# from langchain_google_community import GoogleDriveLoader
from langchain_community.document_loaders import GoogleDriveLoader

from langchain_core.documents import Document

# Import Interface từ tầng Domain
from app.domain.interfaces.document_provider import IDocumentProvider
from app.core.config import settings

DRIVE_NEW_FOLDER_ID = settings.drive_new_folder_id
DRIVE_PROCESSED_FOLDER_ID = settings.drive_processed_folder_id
DRIVE_GROUND_TRUTH_FOLDER_ID = settings.drive_ground_truth_folder_id
# Resolve credentials.json từ backend root directory (tự động, không phụ thuộc cwd)
_backend_dir = (
    Path(__file__).resolve().parents[3]
)  # Up 3 levels: external/ -> infrastructure/ -> app/ -> backend/
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

    def get_file_id_by_name(self, file_name: str, folder_id: str) -> str:
        """Tìm ID của một file cụ thể trong một thư mục cụ thể."""
        try:
            query = (
                f"'{folder_id}' in parents and name = '{file_name}' and trashed = false"
            )
            results = (
                self.service.files()
                .list(q=query, fields="files(id, name)", pageSize=1)
                .execute()
            )

            items = results.get("files", [])
            if not items:
                return None
            return items[0]["id"]
        except Exception as e:
            print(f"❌ Lỗi khi tìm file {file_name} trên Drive: {str(e)}")
            return None

    def download_json(self, file_id: str):
        """Tải file JSON từ Drive thẳng vào RAM (không lưu xuống ổ cứng)."""
        try:
            request = self.service.files().get_media(fileId=file_id)
            fh = io.BytesIO()  # Tạo bộ đệm trên RAM
            downloader = MediaIoBaseDownload(fh, request)

            done = False
            while done is False:
                status, done = downloader.next_chunk()

            # Đọc byte từ RAM và ép kiểu thành JSON (List/Dict)
            fh.seek(0)
            json_data = json.loads(fh.read().decode("utf-8"))
            return json_data

        except Exception as e:
            print(f"❌ Lỗi khi tải và đọc file JSON (ID: {file_id}): {str(e)}")
            return None
