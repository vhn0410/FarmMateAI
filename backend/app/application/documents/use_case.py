import os
import uuid
from app.domain.interfaces.document_provider import IDocumentProvider
from app.domain.interfaces.vector_db import IVectorStoreProvider
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)


class DocumentUseCase:
    """
    Use Case cho việc đồng bộ tài liệu từ provider và lưu vào vector store.

    Sử dụng Dependency Injection cho cả document provider và vector store provider.
    """

    def __init__(
        self, provider: IDocumentProvider, vector_store_provider: IVectorStoreProvider
    ):
        """
        Khởi tạo DocumentUseCase với Dependency Injection.

        :param provider: Implementation của IDocumentProvider (ví dụ: GoogleDriveProvider)
        :param vector_store_provider: Implementation của IVectorStoreProvider (ví dụ: PGVectorProvider)
        """
        self.provider = provider
        self.vector_store_provider = vector_store_provider

    def sync_documents(self):
        """
        Đồng bộ tài liệu từ document provider, chunk hóa, và lưu vào vector store.

        :return: Status message
        """
        # 1. Lấy tài liệu mới từ provider
        raw_documents = self.provider.fetch_new_documents()

        if not raw_documents:
            return "Không có tài liệu mới"

        print(f"Đã load thành công {len(raw_documents)} tài liệu thô.")

        # 2. Cấu hình Splitters
        headers_to_split_on = [
            ("#", "Header_1"),
            ("##", "Header_2"),
            ("###", "Header_3"),
        ]

        markdown_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=headers_to_split_on, strip_headers=False
        )

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1200, chunk_overlap=150
        )

        # 3. Tiến hành Chunking & Gắn Metadata
        final_chunks = []
        processed_file_ids = set()
        for doc in raw_documents:
            source_file = doc.metadata.get("source", "Unknown")

            file_id_for_moving = source_file
            if "drive.google.com/file/d/" in source_file:
                # Splits the URL at '/d/' and takes the ID part before '/view'
                file_id_for_moving = source_file.split("/d/")[1].split("/")[0]
            processed_file_ids.add(file_id_for_moving)

            file_name = doc.metadata.get("title") or doc.metadata.get("name")
            
            # Nếu Loader không trả về tên, ta bắt buộc phải dùng Fallback
            if not file_name:
                if "drive.google.com" in source_file:
                    # Tránh hiển thị chữ "view" vô nghĩa, ta dùng ID rút gọn làm tên tạm
                    file_name = f"Tài_liệu_Drive_{file_id_for_moving[:6]}" 
                else:
                    # Nếu là đường dẫn local (C:/docs/file.pdf), basename mới hoạt động đúng
                    file_name = os.path.basename(source_file)

            # Cắt Lần 1: Theo cấu trúc Markdown
            structure_chunks = markdown_splitter.split_text(doc.page_content)

            # Cắt Lần 2: Theo độ dài ký tự
            fallback_chunks = text_splitter.split_documents(structure_chunks)

            for i, chunk in enumerate(fallback_chunks):
                chunk.metadata["source"] = source_file
                chunk.metadata["file_id"] = file_id_for_moving
                chunk.metadata["file_name"] = file_name
                chunk.metadata["chunk_id"] = str(uuid.uuid4())
                chunk.metadata["chunk_index"] = i

                # Phân quyền mẫu như trong notebook
                if "bao_mat" in file_name.lower():
                    chunk.metadata["allowed_role"] = "admin"
                else:
                    chunk.metadata["allowed_role"] = "public"

                # Xây dựng hierarchy
                h1 = chunk.metadata.get("Header_1", "Không xác định")
                h2 = chunk.metadata.get("Header_2", "Không xác định")
                h3 = chunk.metadata.get("Header_3", "")
                hierarchy = f"{h1} > {h2}" + (f" > {h3}" if h3 else "")
                chunk.metadata["document_hierarchy"] = hierarchy

                final_chunks.append(chunk)

        print(f"Đã cắt thành {len(final_chunks)} chunks. Đang lưu vào vector store...")

        # 4. Lưu vào vector store thông qua provider (Dependency Injection)
        self.vector_store_provider.add_documents(final_chunks)
        print(" Đã lưu thành công vào Database.")

        # 5. ĐÁNH DẤU HOÀN TẤT BẰNG CÁCH DI CHUYỂN FILE
        print("Đang di chuyển các file đã xử lý...")
        for file_id in processed_file_ids:
            if file_id:  # Đảm bảo file_id hợp lệ
                self.provider.mark_as_processed(file_id)

        print("Quá trình Ingestion hoàn tất 100%!")

        return "Thành công"
