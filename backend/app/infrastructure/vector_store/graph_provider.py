import os
import logging
from typing import List, Any
from langchain_neo4j import Neo4jGraph, Neo4jVector
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.core.config import settings
from app.infrastructure.vector_store.pgvector_provider import get_huggingface_embeddings

logger = logging.getLogger(__name__)

class Neo4jGraphProvider:
    """
    Manages connection to Neo4j and provides Graph RAG query functions.
    """

    def __init__(self):
        try:
            # Get Neo4j connection info from environment variables
            self.uri = os.environ.get("NEO4J_URI", "bolt://neo4j:7687")
            self.username = os.environ.get("NEO4J_USERNAME", "neo4j")
            self.password = os.environ.get("NEO4J_PASSWORD", "farmmatepassword")

            self.graph = Neo4jGraph(
                url=self.uri,
                username=self.username,
                password=self.password
            )
            
            # Đảm bảo Vector Index luôn tồn tại kể cả khi Graph chưa có data
            try:
                self.graph.query(
                    "CREATE VECTOR INDEX entity_index IF NOT EXISTS "
                    "FOR (n:__Entity__) ON (n.embedding) "
                    "OPTIONS {indexConfig: {`vector.dimensions`: 768, `vector.similarity_function`: 'cosine'}}"
                )
            except Exception as index_e:
                logger.warning(f"Could not create entity_index automatically: {index_e}")
            
            # Load embeddings for Vector Search on Graph Nodes
            self.embeddings = get_huggingface_embeddings(settings.huggingface_embedding_model)
            
            self.llm = ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0,
                api_key=settings.openai_api_key,
                base_url=settings.openai_api_base
            )
            logger.info("Successfully connected to Neo4j Graph Database.")
        except Exception as e:
            logger.error(f"Error initializing Neo4jGraphProvider: {e}")
            self.graph = None

    def add_graph_documents(self, graph_documents: List[Any]):
        """
        Saves a list of GraphDocuments (nodes, relationships) to Neo4j.
        Neo4jGraph will automatically merge duplicate nodes/relationships based on their names.
        However, to append provenance (sources), we execute a custom Cypher query.
        """
        if not self.graph:
            logger.error("No Neo4j connection. Cannot save Graph.")
            raise Exception("Neo4j database is offline or unreachable.")
            
        try:
            # baseEntityLabel=True adds a common Label to all Nodes (e.g., __Entity__)
            self.graph.add_graph_documents(graph_documents, baseEntityLabel=True)
            logger.info(f"Inserted {len(graph_documents)} Graph Documents into Neo4j.")
            
            # Record provenance: A relationship can originate from multiple files
            # Therefore we save file_id into a `file_ids` array on the relationship
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
                
            # Update Vector Index for Graph Nodes
            logger.info("Updating Vector Index for Graph Nodes...")
            Neo4jVector.from_existing_graph(
                embedding=self.embeddings,
                url=self.uri,
                username=self.username,
                password=self.password,
                index_name='entity_index',
                node_label='__Entity__',
                text_node_properties=['id'], 
                embedding_node_property='embedding',
            )
            logger.info("Vector Index for Graph Nodes updated successfully.")
                
        except Exception as e:
            logger.error(f"Error saving Graph to Neo4j: {e}")
            raise e

    def query_graph_context(self, query: str, file_ids: List[str] = None) -> str:
        """
        1. Embeds the user query to perform Vector Search on the Graph Database.
        2. Retrieves the top relevant entities using the vector index.
        3. Uses Cypher Query to fetch 1-hop relationships around those specific Entities.
        4. Optionally filters the relationships by a list of allowed file_ids.
        5. Formats the results into a text string (Graph Facts).
        """
        if not self.graph:
            logger.error("No Neo4j connection. Cannot query Graph.")
            raise Exception("Neo4j database is offline or unreachable.")

        try:
            print("\n🕸️ [GRAPH SEARCH RUNNING]", flush=True)
            print(f"👉 Câu hỏi: {query}", flush=True)
            if file_ids:
                print(f"👉 Lọc theo file_ids: {file_ids}", flush=True)
            
            # Embed the user query
            query_embedding = self.embeddings.embed_query(query)
            
            # Cypher query for native vector search to find top 5 relevant entities
            vector_search_cypher = """
            CALL db.index.vector.queryNodes('entity_index', 5, $query_embedding)
            YIELD node, score
            RETURN node.id AS source, score
            """
            records = self.graph.query(vector_search_cypher, params={"query_embedding": query_embedding})
            
            entities = []
            print("--- Top Graph Entities (Vector Search) ---", flush=True)
            for i, record in enumerate(records):
                source = record.get("source")
                score = record.get("score")
                if source:
                    entities.append(source)
                    print(f"  > 🔍 Entity {i+1}: {source} | Score: {score:.4f}", flush=True)
            
            if not entities:
                print("  > 🤖 Không tìm thấy Entity nào phù hợp trong Graph.", flush=True)
                print("-" * 40 + "\n", flush=True)
                return ""
                
            graph_facts = []
            
            # Refresh Graph Schema just in case
            self.graph.refresh_schema()

            if file_ids:
                # Clean file_ids to match how they are stored (without .pdf or .md)
                clean_file_ids = [f.replace(".pdf", "").replace(".md", "") for f in file_ids]
                hop_cypher = """
                MATCH p=(n)-[r*1..2]-(m)
                WHERE n.id IN $entities
                UNWIND relationships(p) AS rel
                WITH DISTINCT rel
                WHERE size([x IN $file_ids WHERE x IN rel.file_ids]) > 0
                WITH rel, startNode(rel) AS src, endNode(rel) AS tgt
                ORDER BY COUNT { (tgt)--() } DESC
                LIMIT 40
                RETURN src.id AS source, type(rel) AS relation, tgt.id AS target, rel.file_ids AS file_ids
                """
                hop_records = self.graph.query(hop_cypher, params={"entities": entities, "file_ids": clean_file_ids})
            else:
                hop_cypher = """
                MATCH p=(n)-[r*1..2]-(m)
                WHERE n.id IN $entities
                UNWIND relationships(p) AS rel
                WITH DISTINCT rel
                WITH rel, startNode(rel) AS src, endNode(rel) AS tgt
                ORDER BY COUNT { (tgt)--() } DESC
                LIMIT 40
                RETURN src.id AS source, type(rel) AS relation, tgt.id AS target, rel.file_ids AS file_ids
                """
                hop_records = self.graph.query(hop_cypher, params={"entities": entities})
            
            for record in hop_records:
                source = record.get("source")
                rel = record.get("relation")
                target = record.get("target")
                rel_file_ids = record.get("file_ids", [])
                source_str = ", ".join(rel_file_ids) if rel_file_ids else "Unknown"
                
                fact = f"- {source} [{rel}] {target} (Source files: {source_str})"
                if fact not in graph_facts:
                    graph_facts.append(fact)
                    
            if graph_facts:
                print(f"  > 🔗 Trích xuất thành công {len(graph_facts)} relationships (up to 2-hop & sorted by Degree Centrality).", flush=True)
                print("-" * 40 + "\n", flush=True)
                return "\n".join(graph_facts)
            else:
                print("  > 🤖 Không tìm thấy relationships nào liên quan.", flush=True)
                print("-" * 40 + "\n", flush=True)
                return ""
                
        except Exception as e:
            print(f"[Graph Search Lỗi]: {e}", flush=True)
            return ""

    def delete_graph_by_file_id(self, file_id: str):
        """
        Removes file_id from the `file_ids` property of all Relationships.
        Then deletes relationships that no longer belong to any file.
        Finally deletes all isolated (orphan) nodes.
        """
        if not self.graph:
            logger.error("No Neo4j connection. Cannot delete Graph.")
            raise Exception("Neo4j database is offline or unreachable.")
            
        try:
            # 1. Remove file_id from the file_ids array of all relationships
            remove_file_id_query = """
            MATCH ()-[r]->() 
            WHERE $file_id IN r.file_ids
            SET r.file_ids = [x IN r.file_ids WHERE x <> $file_id]
            """
            self.graph.query(remove_file_id_query, params={"file_id": file_id})
            
            # 2. Delete empty relationships (not belonging to any file)
            delete_empty_edges_query = """
            MATCH ()-[r]->() 
            WHERE size(r.file_ids) = 0 OR r.file_ids IS NULL
            DELETE r
            """
            self.graph.query(delete_empty_edges_query)
            
            # 3. Delete orphan nodes (having no edges)
            delete_orphan_nodes_query = """
            MATCH (n) 
            WHERE COUNT { (n)--() } = 0 
            DELETE n
            """
            self.graph.query(delete_orphan_nodes_query)
            
            logger.info(f"Cleaned up Graph for file: {file_id}. Shared Nodes/Edges are safely kept.")
        except Exception as e:
            logger.error(f"Error deleting Graph for file_id {file_id}: {e}")
            raise e

    def get_graph_by_file_id(self, file_id: str) -> dict:
        """
        Retrieves the graph (nodes and relationships) related to a specific file_id.
        Returns a format suitable for rendering a Force Graph.
        """
        if not self.graph:
            return {"nodes": [], "links": []}

        try:
            # Query to find all relationships belonging to this file_id
            # Note: file_ids is an array stored on each relationship
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
            
            # Clean file_id before searching
            clean_file_id = file_id.replace(".pdf", "").replace(".md", "")
            records = self.graph.query(query, params={"file_id": clean_file_id})
            
            nodes_dict = {}
            links = []
            
            for row in records:
                source = row["source_id"]
                target = row["target_id"]
                
                # Prevent duplicate nodes using a dictionary
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
            logger.error(f"Error getting graph by file_id {file_id}: {e}")
            return {"nodes": [], "links": []}
