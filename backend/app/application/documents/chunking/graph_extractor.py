import logging
from typing import List, Any
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from app.core.config import settings
from pydantic import BaseModel, Field
from langchain_community.graphs.graph_document import Node as GraphNode, Relationship as GraphRelationship, GraphDocument

class ExtractedNode(BaseModel):
    id: str = Field(description="Name or human-readable unique identifier of the entity (e.g., 'Lúa', 'ĐBSCL'). Capitalize properly.")
    type: str = Field(description="Type of the node. Must be one of the allowed node types.")

class ExtractedRelationship(BaseModel):
    source_node_id: str = Field(description="ID of the source node.")
    source_node_type: str = Field(description="Type of the source node.")
    target_node_id: str = Field(description="ID of the target node.")
    target_node_type: str = Field(description="Type of the target node.")
    type: str = Field(description="Type of the relationship. Must be one of the allowed relationship types.")
    description: str = Field(description="REQUIRED: A detailed explanation of this relationship. Must capture any complex conditions (weather, soil, dependencies). If it is a simple relationship, just write a brief description.")

    def __init__(self, **data):
        super().__init__(**data)
        # Flip direction if it extracted Fertilizer -> PRODUCES -> Organization
        if self.type == "PRODUCES" and self.source_node_type in ["Fertilizer", "Pesticide"] and self.target_node_type == "Organization":
            # Swap source and target
            self.source_node_id, self.target_node_id = self.target_node_id, self.source_node_id
            self.source_node_type, self.target_node_type = self.target_node_type, self.source_node_type

class KnowledgeGraphExtraction(BaseModel):
    nodes: List[ExtractedNode] = Field(default_factory=list)
    relationships: List[ExtractedRelationship] = Field(default_factory=list)

class SynonymPair(BaseModel):
    original: str = Field(description="The original node name.")
    standardized: str = Field(description="The standardized synonym node name.")

class EntityResolutionOutput(BaseModel):
    resolved_entities: List[SynonymPair] = Field(description="List of synonym mappings.")

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
            "EnvironmentalIssue", # Vấn đề môi trường (vd: Suy thoái đất, Xâm nhập mặn, Bạc màu đất, Hạn hán)
            "Pesticide",     # Thuốc bảo vệ thực vật
            "Fertilizer",    # Phân bón
            "Location",      # Vị trí/Vùng miền
            "FarmingTechnique", # Kỹ thuật canh tác
            "SoilType",      # Loại đất
            "WeatherCondition", # Điều kiện thời tiết
            "Organization"   # Tổ chức/Công ty
        ]
        
        # Định nghĩa các loại Relationship cho phép (để chuẩn hóa graph)
        allowed_relationships = [
            "AFFECTS",        # Disease AFFECTS Crop
            "CURES",          # Pesticide CURES Disease
            "REQUIRES",       # Crop REQUIRES Fertilizer/FarmingTechnique
            "GROWS_IN",       # Crop GROWS_IN Location/SoilType
            "CAUSES",         # WeatherCondition CAUSES Disease
            "PREVENTS",       # FarmingTechnique PREVENTS Disease
            "INCREASES_RISK_OF",
            "CO_OCCURS_WITH",
            "DEPENDS_ON",
            "PRODUCES",       # Organization PRODUCES Fertilizer/Pesticide
            "RESOLVES",       # Fertilizer/FarmingTechnique RESOLVES SoilType/Disease
            "IMPROVES",       # Fertilizer/FarmingTechnique IMPROVES Crop/SoilType
            "RELATES_TO"      # Generic fallback relationship
        ]

        system_prompt = (
            "You are an expert agricultural data extractor. Your task is to extract a knowledge graph from the given text.\n"
            "Allowed Node Types: {allowed_nodes}\n"
            "Allowed Relationship Types: {allowed_relationships}\n\n"
            "IMPORTANT INSTRUCTIONS:\n"
            "1. Do NOT extract document titles, people's names (e.g. Ts., Pgs., Mr.), acronyms (unless widely known like ĐBSCL), or generic terms.\n"
            "2. ONLY extract genuine, universally recognized agricultural entities and organizations. Keep node IDs concise and precise. DO NOT prepend the Node Type to the Node ID (e.g., use 'BioZinc Plus' instead of 'Fertilizer: BioZinc Plus').\n"
            "3. The 'description' field in relationships is STRICTLY REQUIRED. Use it to detail complex, multi-conditional dependencies.\n"
            "4. Make sure node IDs exactly match between the Nodes list and Relationships list.\n"
            "5. Extract explicit and implicit causal links (e.g. if a problem requires a solution, link them with REQUIRES or RESOLVES).\n"
            "6. WARNING: Be very careful with directionality. Correct: Node(id='AgriTech VN', type='Organization') -[PRODUCES]-> Node(id='BioZinc Plus', type='Fertilizer'). Correct: Node(id='BioZinc Plus', type='Fertilizer') -[RESOLVES]-> Node(id='Suy thoái đất', type='SoilType')."
        )
        
        self.extraction_prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{text}")
        ])
        
        self.extraction_chain = self.extraction_prompt | self.llm.with_structured_output(KnowledgeGraphExtraction, method="function_calling")
        self.allowed_nodes = allowed_nodes
        self.allowed_relationships = allowed_relationships

    def _resolve_synonyms_with_llm(self, unique_node_ids: List[str]) -> dict:
        """
        Gom nhóm các từ đồng nghĩa (Ví dụ: Lúa mùa, Cây lúa -> Lúa)
        """
        if not unique_node_ids:
            return {}
            
        print("Đang chạy LLM Entity Resolution để khử trùng lặp...", flush=True)
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert agricultural ontologist. Group synonyms, acronyms, cross-language translations (e.g., English to Vietnamese), and variations from the provided list of entities into a single standardized, concise Vietnamese name. Return a list of pairs mapping the original names to the standardized name.\n\nCRITICAL INSTRUCTIONS:\n- Map English terms to Vietnamese if a Vietnamese equivalent exists (e.g. 'Fertilizer: Organic Fertilizer' -> 'Phân Hữu Cơ').\n- Standardize agricultural terms (e.g. 'Phân ủ hữu cơ', 'Phân hữu cơ truyền thống' -> 'Phân Hữu Cơ').\n- Standardize environmental issues (e.g. 'Bạc màu đất', 'Bạc màu', 'Suy thoái lớp đất' -> 'Suy Thoái Đất').\n- Do not modify names that are already concise and distinct. Do not invent new names not present in the semantic meaning."),
            ("human", "Entities: {entities}")
        ])
        chain = prompt | self.llm.with_structured_output(EntityResolutionOutput, method="function_calling")
        try:
            result = chain.invoke({"entities": unique_node_ids})
            return {pair.original: pair.standardized for pair in result.resolved_entities}
        except Exception as e:
            print(f"Lỗi Entity Resolution: {e}", flush=True)
            return {}

    def extract_graph_documents(self, documents: List[Document]) -> List[Any]:
        """
        Chuyển đổi danh sách Document text thành GraphDocument (chứa nodes và edges).
        Bổ sung Provenance (thêm chunk_id và source vào thuộc tính của relationships).
        Đã tích hợp Entity Resolution để gom nhóm các Node đồng nghĩa.
        """
        print(f"Bắt đầu trích xuất Graph cho {len(documents)} chunks...", flush=True)
        
        try:
            raw_graph_documents = []
            for i, doc in enumerate(documents):
                print(f"Đang trích xuất Graph cho chunk {i+1}/{len(documents)}...", flush=True)
                try:
                    result: KnowledgeGraphExtraction = self.extraction_chain.invoke({
                        "text": doc.page_content,
                        "allowed_nodes": ", ".join(self.allowed_nodes),
                        "allowed_relationships": ", ".join(self.allowed_relationships)
                    })
                    
                    if result:
                        # Convert Pydantic Models to LangChain GraphDocument
                        # Lớp 1: Lọc bỏ các Node bị gán nhãn Unknown
                        nodes = [GraphNode(id=n.id, type=n.type) for n in result.nodes if n.type != "Unknown"]
                        rels = []
                        for r in result.relationships:
                            # Lớp 2: Lọc bỏ các Mối quan hệ chứa rác hoặc không xác định
                            if r.source_node_type == "Unknown" or r.target_node_type == "Unknown" or r.type == "RELATED_TO":
                                continue
                                
                            source_node = GraphNode(id=r.source_node_id, type=r.source_node_type)
                            target_node = GraphNode(id=r.target_node_id, type=r.target_node_type)
                            rel = GraphRelationship(
                                source=source_node, 
                                target=target_node, 
                                type=r.type,
                                properties={"description": r.description} if r.description else {}
                            )
                            rels.append(rel)
                        
                        graph_doc = GraphDocument(nodes=nodes, relationships=rels, source=doc)
                        raw_graph_documents.append(graph_doc)
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
                
            # 3. Entity Resolution (Khử trùng lặp)
            unique_node_ids = set()
            for doc in graph_documents:
                for node in doc.nodes:
                    unique_node_ids.add(node.id)
            
            resolution_map = self._resolve_synonyms_with_llm(list(unique_node_ids))
            if resolution_map:
                print(f"Bản đồ gom nhóm Node: {resolution_map}", flush=True)
                for doc in graph_documents:
                    # Cập nhật ID của nodes
                    for node in doc.nodes:
                        if node.id in resolution_map:
                            node.id = resolution_map[node.id]
                    # Cập nhật ID của relationships
                    for rel in doc.relationships:
                        if rel.source.id in resolution_map:
                            rel.source.id = resolution_map[rel.source.id]
                        if rel.target.id in resolution_map:
                            rel.target.id = resolution_map[rel.target.id]
                
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
