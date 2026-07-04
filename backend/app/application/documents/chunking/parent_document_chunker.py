import uuid
from typing import List
from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from app.application.documents.chunking.base_chunker import IChunker

class ParentDocumentChunker(IChunker):
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        # Splitting based on markdown headers first
        self.markdown_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[
                ("#", "Header_1"),
                ("##", "Header_2"),
                ("###", "Header_3"),
            ],
            strip_headers=False,
        )
        
        # Then chunk the parents into children
        self.child_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    def chunk(self, text: str, source: str = "Unknown") -> List[Document]:
        # 1. Create Parent chunks
        parent_docs = self.markdown_splitter.split_text(text)
        
        child_docs = []
        # 2. For each parent, generate child chunks and link them
        for parent in parent_docs:
            parent_id = str(uuid.uuid4())
            
            # Enrich parent metadata
            parent.metadata["source"] = source
            parent.metadata["chunk_type"] = "parent"
            parent.metadata["parent_id"] = parent_id
            
            hierarchy_parts = [parent.metadata.get(f"Header_{i}", "") for i in range(1, 4)]
            hierarchy = " > ".join([h for h in hierarchy_parts if h])
            parent.metadata["document_hierarchy"] = hierarchy if hierarchy else "Không xác định"
            
            # Split into children
            children = self.child_splitter.split_documents([parent])
            for child in children:
                child.metadata["chunk_type"] = "child"
                # Keep reference to parent id
                child.metadata["parent_id"] = parent_id
                child_docs.append(child)
                
        # Return only children for evaluation (as they are the ones embedded and retrieved)
        return child_docs
