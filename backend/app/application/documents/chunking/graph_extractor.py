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

        # Instructions bổ sung để ngăn chặn LLM hallucinate (zero-shot limitation)
        additional_instructions = (
            "IMPORTANT: Do NOT extract document titles, organization names, people's names (e.g. starting with Ts., Pgs., Mr.), "
            "acronyms, or generic terms as 'Crop' or 'FarmingTechnique'. "
            "ONLY extract genuine, universally recognized agricultural entities. Keep node IDs concise and precise."
        )

        # Khởi tạo Graph Transformer
        self.transformer = LLMGraphTransformer(
            llm=self.llm,
            allowed_nodes=allowed_nodes,
            allowed_relationships=allowed_relationships,
            node_properties=["description"],
            relationship_properties=["description"],
            additional_instructions=additional_instructions
        )

    def extract_graph_documents(self, documents: List[Document]) -> List[Any]:
        """
        Chuyển đổi danh sách Document text thành GraphDocument (chứa nodes và edges).
        Bổ sung Provenance (thêm chunk_id và source vào thuộc tính của relationships).
        """
        print(f"Bắt đầu trích xuất Graph cho {len(documents)} chunks...", flush=True)
        
        try:
            raw_graph_documents = []
            for i, doc in enumerate(documents):
                print(f"Đang trích xuất Graph cho chunk {i+1}/{len(documents)}...", flush=True)
                try:
                    result = self.transformer.convert_to_graph_documents([doc])
                    if result:
                        raw_graph_documents.extend(result)
                except Exception as chunk_e:
                    print(f"Lỗi ở chunk {i+1}: {chunk_e}", flush=True)
                    
            graph_documents = []
            
            # Post-processing: Filter out noisy nodes
            forbidden_keywords = ["sổ tay", "quyết định", "bộ nông nghiệp", "ts.", "pgs", "quy trình", "đề án"]
            
            for i, graph_doc in enumerate(raw_graph_documents):
                valid_nodes = []
                deleted_node_ids = set()
                
                # 1. Filter Nodes
                for node in graph_doc.nodes:
                    node_id_lower = node.id.lower()
                    # Condition to delete: > 40 chars, or contains forbidden keyword, or is entirely uppercase (often noisy acronyms, but we allow short ones like SRI, IPM if they are known)
                    is_too_long = len(node.id) > 40
                    has_forbidden = any(kw in node_id_lower for kw in forbidden_keywords)
                    
                    if is_too_long or has_forbidden:
                        deleted_node_ids.add(node.id)
                        print(f"Filtered out noisy node: {node.id}", flush=True)
                    else:
                        valid_nodes.append(node)
                
                # 2. Filter Relationships pointing to deleted nodes
                valid_relationships = []
                for rel in graph_doc.relationships:
                    if rel.source.id not in deleted_node_ids and rel.target.id not in deleted_node_ids:
                        valid_relationships.append(rel)
                
                # Update the graph document
                graph_doc.nodes = valid_nodes
                graph_doc.relationships = valid_relationships
                graph_documents.append(graph_doc)
                
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

            print(f"Đã trích xuất thành công {len(graph_documents)} Graph Documents.", flush=True)
            return graph_documents
        except Exception as e:
            print(f"Lỗi khi trích xuất Graph: {e}", flush=True)
            return []
