import os
import sys

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.infrastructure.vector_store.graph_provider import Neo4jGraphProvider

provider = Neo4jGraphProvider()
print("=== NODES ===")
res = provider.graph.query("MATCH (n) WHERE n.id CONTAINS 'AgriTech' OR n.id CONTAINS 'BioZinc' OR n.id CONTAINS 'phun sương' RETURN n.id, labels(n)")
for r in res:
    print(r)

print("=== RELATIONSHIPS ===")
res2 = provider.graph.query("MATCH (n)-[r]-(m) WHERE n.id CONTAINS 'AgriTech' OR n.id CONTAINS 'BioZinc' OR n.id CONTAINS 'phun sương' RETURN n.id, type(r), m.id")
for r in res2:
    print(r)
