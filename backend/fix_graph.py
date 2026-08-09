import os
import sys

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.infrastructure.vector_store.graph_provider import Neo4jGraphProvider

provider = Neo4jGraphProvider()

# Fix the directionality error caused by LLM extraction hallucination
fix_query = """
MATCH (a {id: 'BioZinc Plus'})-[r:PRODUCES]->(b {id: 'AgriTech VN'})
CREATE (b)-[new_r:PRODUCES]->(a)
SET new_r = properties(r)
DELETE r
"""
provider.graph.query(fix_query)

fix_query_2 = """
MATCH (a {id: 'EcoShield'})-[r:PRODUCES]->(b {id: 'AgriTech VN'})
CREATE (b)-[new_r:PRODUCES]->(a)
SET new_r = properties(r)
DELETE r
"""
provider.graph.query(fix_query_2)

print("Đã đảo ngược mũi tên quan hệ thành công!")
