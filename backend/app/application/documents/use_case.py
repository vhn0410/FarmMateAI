import os
import uuid
from app.domain.interfaces.document_provider import IDocumentProvider
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)
from app.infrastructure.vector_store.pgvector_db import get_vector_store


class DocumentUseCase:
    # 1. BẮT BUỘC TRUYỀN VÀO TỪ BÊN NGOÀI (Dependency Injection)
    def __init__(self, provider: IDocumentProvider):
        self.provider = provider

    def sync_documents(self):
        # 2. Sử dụng các hàm của Interface một cách an toàn
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

            file_name = os.path.basename(source_file)

            # Cắt Lần 1: Theo cấu trúc Markdown
            structure_chunks = markdown_splitter.split_text(doc.page_content)

            # Cắt Lần 2: Theo độ dài ký tự
            fallback_chunks = text_splitter.split_documents(structure_chunks)

            for i, chunk in enumerate(fallback_chunks):
                chunk.metadata["source"] = source_file
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

        print(f"Đã cắt thành {len(final_chunks)} chunks. Đang lưu vào PGVector...")

        # 4. Lưu vào PGVector
        vector_store = get_vector_store()
        vector_store.add_documents(final_chunks)
        print(" Đã lưu thành công vào Database.")
        # 5. ĐÁNH DẤU HOÀN TẤT BẰNG CÁCH DI CHUYỂN FILE
        print("Đang di chuyển các file đã xử lý...")
        for file_id in processed_file_ids:
            if file_id:  # Đảm bảo file_id hợp lệ
                self.provider.mark_as_processed(file_id)

        print("Quá trình Ingestion hoàn tất 100%!")

        return "Thành công"
