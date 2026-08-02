import os
import sys

# Fix Windows encoding issue
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.infrastructure.vector_store.graph_provider import Neo4jGraphProvider

provider = Neo4jGraphProvider()
print("=== ALL NODES IN GRAPH ===")
res = provider.graph.query("MATCH (n:__Entity__) RETURN n.id AS id, n.type AS type")
for r in res:
    print(r)

