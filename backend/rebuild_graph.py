import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.infrastructure.vector_store.pgvector_provider import PGVectorProvider
from app.infrastructure.vector_store.graph_provider import Neo4jGraphProvider
from app.application.documents.chunking.graph_extractor import GraphExtractor

def rebuild_graph():
    print("Rebuilding Graph from PGVector chunks...")
    vector_db = PGVectorProvider()
    graph_db = Neo4jGraphProvider()
    extractor = GraphExtractor()
    
    docs = vector_db._vector_store.similarity_search("lúa gạo phân bón ĐBSCL canh tác công ty", k=100)
    
    unique_docs = {}
    for doc in docs:
        if doc.page_content not in unique_docs:
            unique_docs[doc.page_content] = doc
            
    doc_list = list(unique_docs.values())
    print(f"Found {len(doc_list)} unique chunks to process.")
    
    # Clear existing graph
    print("Clearing existing graph...")
    graph_db.graph.query("MATCH (n) DETACH DELETE n")
    
    try:
        graph_documents = extractor.extract_graph_documents(doc_list)
        if graph_documents:
            graph_db.add_graph_documents(graph_documents)
            print(f"Successfully added {len(graph_documents)} graph documents to Neo4j.")
        else:
            print("No graph documents were extracted.")
    except Exception as e:
        print(f"Error during extraction/insertion: {e}")
            
    print("Graph rebuild complete.")

if __name__ == "__main__":
    rebuild_graph()
