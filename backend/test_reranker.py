from app.core.config import settings
from app.infrastructure.vector_store.pgvector_provider import PGVectorProvider
from app.infrastructure.llm.gemini_provider import GeminiLLMProvider
from app.agents.skills.rag_agriculture.tool import AgricultureRAGSkill

print("Initializing Providers...")
v = PGVectorProvider()
l = GeminiLLMProvider()

print("Initializing Skill (with Reranker)...")
skill = AgricultureRAGSkill(v, l)

print("Retriever instance:", skill.retriever.__class__.__name__)
print("Running query...")
res = skill.run("How to control brown planthopper infestations in rice")
print("Top Sources extracted:")
for s in res.metadata.get("top_sources", []):
    print("-", s["file_name"], "Score:", s.get("cross_encoder_score", "N/A"))
print("Done!")
