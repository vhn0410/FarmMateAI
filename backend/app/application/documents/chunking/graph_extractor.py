import logging
from typing import List, Any
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI
from langchain_experimental.graph_transformers import LLMGraphTransformer
from app.core.config import settings

logger = logging.getLogger(__name__)

class GraphExtractor:
    """
    Trích xuất Knowledge Graph (Nodes, Relationships) từ văn bản
    bằng cách sử dụng LLMGraphTransformer với Constrained Ontology.
    """

    def __init__(self):
        # Sử dụng ChatOpenAI với config từ môi trường
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            api_key=settings.openai_api_key,
            base_url=settings.openai_api_base
        )
        
        # Định nghĩa các loại Node cho phép (Constrained Ontology)
        allowed_nodes = [
            "Crop",          # Cây trồng (vd: Lúa, Cà phê, Xoài)
            "Disease",       # Bệnh hại (vd: Đạo ôn, Rầy nâu)
            "Pesticide",     # Thuốc bảo vệ thực vật
            "Fertilizer",    # Phân bón
            "Location",      # Vị trí/Vùng miền
            "FarmingTechnique", # Kỹ thuật canh tác
            "SoilType",      # Loại đất
            "WeatherCondition" # Điều kiện thời tiết
        ]
        
        # Định nghĩa các loại Relationship cho phép (để chuẩn hóa graph)
        allowed_relationships = [
            "AFFECTS",        # Disease AFFECTS Crop
            "CURES",          # Pesticide CURES Disease
            "REQUIRES",       # Crop REQUIRES Fertilizer/FarmingTechnique
            "GROWS_IN",       # Crop GROWS_IN Location/SoilType
            "CAUSES",         # WeatherCondition CAUSES Disease
            "PREVENTS"        # FarmingTechnique PREVENTS Disease
        ]

        # Khởi tạo Graph Transformer
        self.transformer = LLMGraphTransformer(
            llm=self.llm,
            allowed_nodes=allowed_nodes,
            allowed_relationships=allowed_relationships,
            node_properties=["description"],
            relationship_properties=["description"]
        )

    def extract_graph_documents(self, documents: List[Document]) -> List[Any]:
        """
        Chuyển đổi danh sách Document text thành GraphDocument (chứa nodes và edges).
        Bổ sung Provenance (thêm chunk_id và source vào thuộc tính của relationships).
        """
        logger.info(f"Bắt đầu trích xuất Graph cho {len(documents)} chunks...")
        
        # Gọi LLMGraphTransformer để trích xuất (tốn thời gian và chi phí API)
        try:
            graph_documents = self.transformer.convert_to_graph_documents(documents)
            
            # Gắn Provenance Tracking
            for i, graph_doc in enumerate(graph_documents):
                original_doc = documents[i]
                source = original_doc.metadata.get("source", "Unknown")
                file_id = original_doc.metadata.get("file_id", "Unknown")
                chunk_id = original_doc.metadata.get("chunk_id", f"chunk_{i}")
                
                # Cập nhật thuộc tính của tất cả các Relationship
                for rel in graph_doc.relationships:
                    # Gán các property. Neo4jGraph.add_graph_documents sẽ biến những thuộc tính này thành properties trên Edge trong DB.
                    rel.properties["source_file"] = f"{source} (ID: {file_id})"
                    rel.properties["file_id"] = file_id
                    rel.properties["chunk_id"] = chunk_id

            logger.info(f"Đã trích xuất thành công {len(graph_documents)} Graph Documents.")
            return graph_documents
        except Exception as e:
            logger.error(f"Lỗi khi trích xuất Graph: {e}")
            return []
