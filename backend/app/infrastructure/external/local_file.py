import os
import shutil
from pathlib import Path
from typing import List
from langchain_core.documents import Document

from app.domain.interfaces.document_provider import IDocumentProvider


class LocalFileSystemProvider(IDocumentProvider):
    """
    Provider quản lý tài liệu lưu trữ cục bộ trên máy chủ (Local File System).
    Hỗ trợ tự động chuyển đổi PDF sang Markdown sử dụng LlamaParse.
    """

    def __init__(self, base_dir: str = "data/knowledge_base"):
        self.base_dir = Path(base_dir)
        self.pdf_dir = self.base_dir / "pdf"
        self.md_dir = self.base_dir / "md"
        self.processed_dir = self.base_dir / "processed"

        # Đảm bảo các thư mục tồn tại
        self.pdf_dir.mkdir(parents=True, exist_ok=True)
        self.md_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)

    def list_pdf_files(self) -> List[dict]:
        """Trả về danh sách các file PDF hiện có trong hệ thống."""
        files = []
        for pdf_path in self.pdf_dir.glob("*.pdf"):
            files.append({
                "id": pdf_path.name,
                "name": pdf_path.name
            })
        # Sắp xếp theo thời gian tạo mới nhất
        files.sort(key=lambda x: (self.pdf_dir /
                   x["name"]).stat().st_mtime, reverse=True)
        return files

    def get_pdf_path(self, file_name: str) -> Path:
        """Lấy đường dẫn tuyệt đối của một file PDF."""
        return self.pdf_dir / file_name

    def get_md_path(self, file_name: str) -> Path:
        """Lấy đường dẫn tuyệt đối của một file MD."""
        stem = Path(file_name).stem
        md_file = self.md_dir / f"{stem}.md"
        if md_file.exists():
            return md_file
        
        processed_file = self.processed_dir / f"{stem}.md"
        if processed_file.exists():
            return processed_file
            
        return md_file

    def save_uploaded_pdf(self, file_name: str, file_bytes: bytes) -> str:
        """Lưu file PDF được upload vào thư mục cục bộ."""
        # Sanitize tên file để tránh lỗi thư mục
        safe_name = file_name.replace(" ", "_")
        pdf_path = self.pdf_dir / safe_name

        with open(pdf_path, "wb") as f:
            f.write(file_bytes)

        return safe_name

    def process_pdf_to_md(self, pdf_file_name: str):
        """
        [Chạy Ngầm] Sử dụng LlamaParse để chuyển PDF thành Markdown.
        """
        pdf_path = self.pdf_dir / pdf_file_name
        if not pdf_path.exists():
            print(f"❌ File không tồn tại: {pdf_path}")
            return

        try:
            print(f"⏳ Đang xử lý bằng AI Vision (LlamaParse): {pdf_file_name}...")
            from llama_parse import LlamaParse
            import asyncio
            
            # Đảm bảo có event loop trong thread ngầm (Background Task)
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            from app.core.config import settings
            
            # Khởi tạo LlamaParse tối ưu cho tài liệu học thuật (Tiếng Việt)
            parser = LlamaParse(
                api_key=settings.llama_cloud_api_key,
                result_type="markdown",
                premium_mode=True,
                language="vi"
            )

            # Gọi API Parse
            documents = parser.load_data(str(pdf_path))

            # Gộp toàn bộ các trang lại thành 1 chuỗi Markdown
            md_text = "\n\n".join([doc.text for doc in documents])

            output_filename = pdf_path.stem + ".md"
            output_path = self.md_dir / output_filename

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(md_text)

            print(f"✅ LlamaParse đã lưu thành công: {output_filename}")

        except Exception as e:
            print(f"❌ Lỗi khi LlamaParse xử lý {pdf_file_name}: {str(e)}")

    def fetch_new_documents(self) -> List[Document]:
        """
        Quét thư mục /md để lấy các file Markdown chưa được đồng bộ vào VectorDB.
        Đóng gói thành đối tượng Document của Langchain.
        """
        documents = []
        for md_path in self.md_dir.glob("*.md"):
            try:
                with open(md_path, "r", encoding="utf-8") as f:
                    content = f.read()

                doc = Document(
                    page_content=content,
                    metadata={
                        "source": md_path.name,
                        "file_id": md_path.stem
                    }
                )
                documents.append(doc)
            except Exception as e:
                print(f"❌ Lỗi đọc file {md_path.name}: {str(e)}")

        return documents

    def mark_as_processed(self, file_id: str) -> None:
        """
        Di chuyển file Markdown đã đồng bộ xong sang thư mục /processed 
        để tránh quét lại trong lần sau.
        """
        md_file = self.md_dir / f"{file_id}.md"
        if md_file.exists():
            shutil.move(str(md_file), str(self.processed_dir / md_file.name))
            print(f"✅ Đã di chuyển {md_file.name} sang processed/")

    def delete_file(self, file_id: str) -> None:
        """Xóa toàn bộ các file vật lý liên quan đến file_id."""
        # 1. Xóa PDF gốc
        pdf_file = self.pdf_dir / f"{file_id}.pdf"
        if pdf_file.exists():
            pdf_file.unlink()
            print(f"🗑️ Đã xóa PDF: {pdf_file.name}")
            
        # 2. Xóa MD thô (nếu chưa processed)
        md_file = self.md_dir / f"{file_id}.md"
        if md_file.exists():
            md_file.unlink()
            print(f"🗑️ Đã xóa MD: {md_file.name}")
            
        # 3. Xóa MD trong processed
        processed_file = self.processed_dir / f"{file_id}.md"
        if processed_file.exists():
            processed_file.unlink()
            print(f"🗑️ Đã xóa Processed MD: {processed_file.name}")
