import os
import boto3
import tempfile
import urllib.parse
from pathlib import Path
from typing import List, Generator
from langchain_core.documents import Document

from app.domain.interfaces.document_provider import IDocumentProvider
from app.core.config import settings


class S3FileSystemProvider(IDocumentProvider):
    """
    Provider quản lý tài liệu lưu trữ trên Amazon S3.
    """

    def __init__(self):
        self.bucket_name = settings.aws_bucket_name
        if not self.bucket_name:
            raise ValueError("AWS_BUCKET_NAME is not configured")

        self.s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
        )
        self.pdf_prefix = "pdf/"
        self.md_prefix = "md/"
        self.processed_prefix = "processed/"
        self.lock_prefix = "locks/"

    def create_lock(self, file_id: str) -> None:
        """Create an empty lock file in S3 to indicate the file is processing."""
        lock_key = f"{self.lock_prefix}{file_id}.lock"
        try:
            self.s3_client.put_object(Bucket=self.bucket_name, Key=lock_key, Body=b"")
        except Exception as e:
            print(f"Error creating lock for {file_id}: {str(e)}")

    def remove_lock(self, file_id: str) -> None:
        """Remove the lock file from S3."""
        lock_key = f"{self.lock_prefix}{file_id}.lock"
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=lock_key)
        except Exception as e:
            print(f"Error removing lock for {file_id}: {str(e)}")

    def is_locked(self, file_id: str) -> bool:
        """Check if the lock file exists in S3."""
        lock_key = f"{self.lock_prefix}{file_id}.lock"
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=lock_key)
            return True
        except Exception:
            return False

    def list_pdf_files(self) -> List[dict]:
        """Trả về danh sách các file PDF hiện có trong S3 bucket (prefix pdf/)."""
        files = []
        try:
            # Lấy danh sách PDF
            pdf_response = self.s3_client.list_objects_v2(Bucket=self.bucket_name, Prefix=self.pdf_prefix)
            pdf_objects = pdf_response.get("Contents", [])

            # Lấy danh sách processed MD để biết status
            processed_response = self.s3_client.list_objects_v2(Bucket=self.bucket_name, Prefix=self.processed_prefix)
            processed_keys = [obj["Key"].replace(self.processed_prefix, "") for obj in processed_response.get("Contents", [])]

            for obj in pdf_objects:
                key = obj["Key"]
                if key == self.pdf_prefix:  # Bỏ qua chính folder (nếu có)
                    continue
                    
                file_name = key.replace(self.pdf_prefix, "")
                stem = Path(file_name).stem
                
                is_processed = f"{stem}.md" in processed_keys
                files.append({
                    "id": file_name,
                    "name": file_name,
                    "status": "ready" if is_processed else "processing",
                    "last_modified": obj["LastModified"].timestamp()
                })

            # Sắp xếp theo thời gian mới nhất
            files.sort(key=lambda x: x["last_modified"], reverse=True)
            
            # Xóa trường last_modified trước khi trả về
            for f in files:
                del f["last_modified"]
                
        except Exception as e:
            print(f"❌ Lỗi khi lấy danh sách file từ S3: {str(e)}")
            
        return files

    def get_pdf_stream(self, file_name: str) -> Generator:
        """Stream PDF từ S3 để Client tải về."""
        s3_key = f"{self.pdf_prefix}{file_name}"
        response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
        return response["Body"].iter_chunks()

    def get_md_content(self, file_name: str) -> str | None:
        """Lấy nội dung file MD từ S3."""
        stem = Path(file_name).stem
        md_filename = f"{stem}.md"
        
        # Check in md_prefix
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=f"{self.md_prefix}{md_filename}")
            return response["Body"].read().decode("utf-8")
        except self.s3_client.exceptions.NoSuchKey:
            pass
            
        # Check in processed_prefix
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=f"{self.processed_prefix}{md_filename}")
            return response["Body"].read().decode("utf-8")
        except self.s3_client.exceptions.NoSuchKey:
            return None

    def save_uploaded_pdf(self, file_name: str, file_bytes: bytes) -> str:
        """Lưu file PDF được upload lên S3."""
        safe_name = file_name.replace(" ", "_")
        s3_key = f"{self.pdf_prefix}{safe_name}"

        # Xóa MD cũ (trong cả md/ và processed/) nếu up đè
        stem = Path(safe_name).stem
        for prefix in [self.md_prefix, self.processed_prefix]:
            try:
                self.s3_client.delete_object(Bucket=self.bucket_name, Key=f"{prefix}{stem}.md")
            except Exception:
                pass

        self.s3_client.put_object(Bucket=self.bucket_name, Key=s3_key, Body=file_bytes)
        return safe_name
        
    def check_pdf_exists(self, file_name: str) -> bool:
        """Kiểm tra PDF có tồn tại trên S3 không."""
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=f"{self.pdf_prefix}{file_name}")
            return True
        except Exception:
            return False

    def process_pdf_to_md(self, pdf_file_name: str):
        """
        [Chạy Ngầm] Sử dụng LlamaParse để chuyển PDF thành Markdown.
        Vì LlamaParse cần file local, ta phải download file từ S3 về máy tạo ra file tạm,
        sau đó parse, rồi upload MD kết quả lên lại S3.
        """
        s3_key = f"{self.pdf_prefix}{pdf_file_name}"
        
        if not self.check_pdf_exists(pdf_file_name):
            print(f"❌ File không tồn tại trên S3: {s3_key}")
            return

        # Tạo file tạm để LlamaParse có thể đọc
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_pdf:
            temp_path = temp_pdf.name
            
        try:
            print(f"📥 Đang tải {pdf_file_name} từ S3 về tạm...")
            self.s3_client.download_file(self.bucket_name, s3_key, temp_path)
            
            print(f"⏳ Đang xử lý bằng AI Vision (LlamaParse): {pdf_file_name}...")
            from llama_parse import LlamaParse
            import asyncio
            
            # Đảm bảo có event loop
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # Khởi tạo LlamaParse
            parser = LlamaParse(
                api_key=settings.llama_cloud_api_key,
                result_type="markdown",
                premium_mode=True,
                language="vi"
            )

            # Gọi API Parse
            documents = parser.load_data(temp_path)
            
            if not documents:
                raise Exception("LlamaParse returned 0 documents! Check your credits or the file validity.")

            # Gộp text
            md_text = "\n\n".join([doc.text for doc in documents])

            # Upload MD lên S3
            output_filename = Path(pdf_file_name).stem + ".md"
            md_key = f"{self.md_prefix}{output_filename}"
            
            self.s3_client.put_object(
                Bucket=self.bucket_name, 
                Key=md_key, 
                Body=md_text.encode("utf-8")
            )

            print(f"✅ Đã xử lý và tải lên S3 thành công: {md_key}")

        except Exception as e:
            print(f"❌ Lỗi khi LlamaParse xử lý {pdf_file_name}: {str(e)}")
            raise e
        finally:
            # Dọn dẹp file tạm
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def fetch_new_documents(self) -> List[Document]:
        """
        Quét bucket (prefix md/) để lấy các file MD chưa được đồng bộ.
        """
        documents = []
        try:
            response = self.s3_client.list_objects_v2(Bucket=self.bucket_name, Prefix=self.md_prefix)
            for obj in response.get("Contents", []):
                key = obj["Key"]
                if key == self.md_prefix:
                    continue
                    
                file_name = key.replace(self.md_prefix, "")
                stem = Path(file_name).stem
                
                # Tải nội dung text trực tiếp từ S3
                obj_resp = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
                content = obj_resp["Body"].read().decode("utf-8")
                
                doc = Document(
                    page_content=content,
                    metadata={
                        "source": file_name,
                        "file_id": stem
                    }
                )
                documents.append(doc)
        except Exception as e:
            print(f"❌ Lỗi khi lấy documents từ S3: {str(e)}")
            
        return documents

    def mark_as_processed(self, file_id: str) -> None:
        """
        Move the Markdown file from md/ to processed/
        S3 doesn't have a move command, so we copy and delete.
        """
        source_key = f"{self.md_prefix}{file_id}.md"
        dest_key = f"{self.processed_prefix}{file_id}.md"
        
        try:
            copy_source = {'Bucket': self.bucket_name, 'Key': source_key}
            self.s3_client.copy_object(CopySource=copy_source, Bucket=self.bucket_name, Key=dest_key)
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=source_key)
            print(f"✅ Moved S3 {file_id}.md to processed/")
        except Exception as e:
            print(f"❌ Error moving file {file_id}.md: {str(e)}")

    def delete_file(self, file_id: str) -> None:
        """Delete all files related to file_id on S3."""
        keys_to_delete = [
            f"{self.pdf_prefix}{file_id}.pdf",
            f"{self.md_prefix}{file_id}.md",
            f"{self.processed_prefix}{file_id}.md",
            f"{self.lock_prefix}{file_id}.lock"
        ]
        
        objects = [{'Key': key} for key in keys_to_delete]
        try:
            self.s3_client.delete_objects(
                Bucket=self.bucket_name,
                Delete={'Objects': objects}
            )
            print(f"🗑️ Deleted all files related to {file_id} on S3.")
        except Exception as e:
            print(f"❌ Error deleting on S3: {str(e)}")
