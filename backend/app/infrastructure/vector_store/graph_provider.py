import os
import logging
from typing import List, Any
from langchain_community.graphs import Neo4jGraph
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.core.config import settings

logger = logging.getLogger(__name__)

class Neo4jGraphProvider:
    """
    Quản lý kết nối tới Neo4j và cung cấp các hàm truy vấn Graph RAG.
    """

    def __init__(self):
        try:
            # Lấy thông tin kết nối Neo4j từ biến môi trường (cần thiết lập trong .env)
            uri = os.environ.get("NEO4J_URI", "bolt://neo4j:7687")
            username = os.environ.get("NEO4J_USERNAME", "neo4j")
            password = os.environ.get("NEO4J_PASSWORD", "farmmatepassword")

            self.graph = Neo4jGraph(
                url=uri,
                username=username,
                password=password
            )
            
            self.llm = ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0,
                api_key=settings.openai_api_key,
                base_url=settings.openai_api_base
            )
            logger.info("Đã kết nối thành công tới Neo4j Graph Database.")
        except Exception as e:
            logger.error(f"Lỗi khi khởi tạo Neo4jGraphProvider: {e}")
            self.graph = None

    def add_graph_documents(self, graph_documents: List[Any]):
        """
        Lưu danh sách GraphDocument (nodes, relationships) vào Neo4j.
        Neo4jGraph sẽ tự động merge các node/relationship bị trùng lặp dựa trên tên.
        Tuy nhiên, để append provenance (sources), ta cần gọi lệnh cypher tuỳ chỉnh hoặc 
        dựa vào cơ chế của LLMGraphTransformer nếu đã gán thuộc tính.
        """
        if not self.graph:
            logger.error("Không có kết nối Neo4j. Không thể lưu Graph.")
            raise Exception("Neo4j database is offline or unreachable.")
            
        try:
            # baseEntityLabel=True giúp tạo thêm một Label chung cho tất cả các Node (vd: __Entity__)
            self.graph.add_graph_documents(graph_documents, baseEntityLabel=True)
            logger.info(f"Đã chèn {len(graph_documents)} Graph Documents vào Neo4j.")
            
            # Ghi nhận provenance: Một relationship có thể xuất phát từ nhiều file khác nhau
            # Do đó ta lưu file_id vào mảng `file_ids` trên relationship
            edges_data = []
            for doc in graph_documents:
                for rel in doc.relationships:
                    file_id = rel.properties.get("file_id")
                    if file_id:
                        edges_data.append({
                            "source_id": rel.source.id,
                            "target_id": rel.target.id,
                            "rel_type": rel.type,
                            "file_id": file_id
                        })
            
            if edges_data:
                provenance_query = """
                UNWIND $edges AS edge
                MATCH (a {id: edge.source_id})-[r]->(b {id: edge.target_id})
                WHERE type(r) = edge.rel_type
                SET r.file_ids = CASE 
                    WHEN r.file_ids IS NULL THEN [edge.file_id]
                    WHEN NOT edge.file_id IN r.file_ids THEN r.file_ids + edge.file_id
                    ELSE r.file_ids
                END
                """
                self.graph.query(provenance_query, params={"edges": edges_data})
                
        except Exception as e:
            logger.error(f"Lỗi khi lưu Graph vào Neo4j: {e}")
            raise e

    def query_graph_context(self, query: str) -> str:
        """
        1. Dùng LLM trích xuất Entities từ câu hỏi của user.
        2. Dùng Cypher Query lấy các mối quan hệ (1-hop) xung quanh các Entities đó.
        3. Format kết quả thành chuỗi văn bản (Graph Facts).
        """
        if not self.graph:
            logger.error("Không có kết nối Neo4j. Không thể truy vấn Graph.")
            raise Exception("Neo4j database is offline or unreachable.")

        # Dùng LLM đơn giản để trích xuất từ khóa chính từ câu hỏi
        extraction_prompt = ChatPromptTemplate.from_template(
            "Extract the main agricultural entities (crops, diseases, pesticides, locations) from this question. "
            "Return ONLY a comma-separated list of entities, no other text.\nQuestion: {query}"
        )
        
        chain = extraction_prompt | self.llm
        try:
            result = chain.invoke({"query": query})
            entities_str = result.content.strip()
            
            if not entities_str:
                return ""
                
            entities = [e.strip() for e in entities_str.split(",") if e.strip()]
            logger.info(f"Trích xuất Entities từ câu hỏi: {entities}")
            
            graph_facts = []
            
            # Khởi tạo Graph Schema nếu chưa có
            self.graph.refresh_schema()

            # Cypher query: Tìm các node có name gần giống với các Entity được trích xuất (có thể dùng Vector Index để xịn hơn,
            # nhưng tạm thời dùng CONTAINS hoặc MATCH case-insensitive để minh họa cơ bản)
            for entity in entities:
                cypher = """
                MATCH (n)-[r]->(m)
                WHERE toLower(n.id) CONTAINS toLower($entity) OR toLower(m.id) CONTAINS toLower($entity)
                RETURN n.id AS source, type(r) AS relation, m.id AS target, r.file_ids AS file_ids
                LIMIT 10
                """
                records = self.graph.query(cypher, params={"entity": entity})
                for record in records:
                    source = record.get("source")
                    rel = record.get("relation")
                    target = record.get("target")
                    file_ids = record.get("file_ids", [])
                    source_str = ", ".join(file_ids) if file_ids else "Unknown"
                    
                    fact = f"- {source} [{rel}] {target} (Nguồn file: {source_str})"
                    if fact not in graph_facts:
                        graph_facts.append(fact)
                        
            if graph_facts:
                logger.info(f"Đã tìm thấy {len(graph_facts)} Graph Facts.")
                return "\n".join(graph_facts)
            else:
                return ""
                
        except Exception as e:
            logger.error(f"Lỗi khi truy vấn Graph Context: {e}")
            return ""

    def delete_graph_by_file_id(self, file_id: str):
        """
        Xóa file_id khỏi thuộc tính `file_ids` của tất cả các Relationships.
        Sau đó xóa các Relationships không còn bất kỳ file_id nào.
        Cuối cùng xóa tất cả các Node không còn liên kết nào (Orphan nodes).
        """
        if not self.graph:
            logger.error("Không có kết nối Neo4j. Không thể xóa Graph.")
            raise Exception("Neo4j database is offline or unreachable.")
            
        try:
            # 1. Gỡ file_id khỏi mảng file_ids của tất cả các mối quan hệ
            remove_file_id_query = """
            MATCH ()-[r]->() 
            WHERE $file_id IN r.file_ids
            SET r.file_ids = [x IN r.file_ids WHERE x <> $file_id]
            """
            self.graph.query(remove_file_id_query, params={"file_id": file_id})
            
            # 2. Xóa các relationship rỗng (không còn thuộc file nào)
            delete_empty_edges_query = """
            MATCH ()-[r]->() 
            WHERE size(r.file_ids) = 0 OR r.file_ids IS NULL
            DELETE r
            """
            self.graph.query(delete_empty_edges_query)
            
            # 3. Xóa tất cả các nodes bị cô lập (không còn bất kỳ cạnh nào)
            delete_orphan_nodes_query = """
            MATCH (n) 
            WHERE COUNT { (n)--() } = 0 
            DELETE n
            """
            self.graph.query(delete_orphan_nodes_query)
            
            logger.info(f"Đã dọn dẹp Graph cho file: {file_id}. Các Node/Edge chung vẫn được giữ lại an toàn.")
        except Exception as e:
            logger.error(f"Lỗi khi xóa Graph cho file_id {file_id}: {e}")
            raise e

    def get_graph_by_file_id(self, file_id: str) -> dict:
        """
        Lấy đồ thị (nodes và relationships) liên quan đến một file_id cụ thể.
        Trả về định dạng phù hợp để vẽ Force Graph.
        """
        if not self.graph:
            return {"nodes": [], "links": []}

        try:
            # Truy vấn tìm tất cả các relationship thuộc file_id này
            # Lưu ý: file_ids là một mảng được lưu trên mỗi relationship
            query = """
            MATCH (n)-[r]->(m)
            WHERE $file_id IN r.file_ids
            RETURN 
                n.id AS source_id, 
                [l IN labels(n) WHERE l <> '__Entity__'][0] AS source_label, 
                type(r) AS rel_type, 
                r.chunk_id AS chunk_id, 
                m.id AS target_id, 
                [l IN labels(m) WHERE l <> '__Entity__'][0] AS target_label
            """
            
            # File ID được sanitize trước khi lưu
            clean_file_id = file_id.replace(".pdf", "").replace(".md", "")
            records = self.graph.query(query, params={"file_id": clean_file_id})
            
            nodes_dict = {}
            links = []
            
            for row in records:
                source = row["source_id"]
                target = row["target_id"]
                
                # Tránh duplicate node bằng dictionary
                if source not in nodes_dict:
                    nodes_dict[source] = {"id": source, "label": row["source_label"] or "Entity"}
                if target not in nodes_dict:
                    nodes_dict[target] = {"id": target, "label": row["target_label"] or "Entity"}
                    
                links.append({
                    "source": source,
                    "target": target,
                    "label": row["rel_type"],
                    "chunk_id": row["chunk_id"]
                })
                
            return {
                "nodes": list(nodes_dict.values()),
                "links": links
            }
        except Exception as e:
            logger.error(f"Lỗi khi get graph by file_id {file_id}: {e}")
            return {"nodes": [], "links": []}
