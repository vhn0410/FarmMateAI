import logging
from typing import Optional, Dict

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_classic.chains import create_retrieval_chain
from langchain_community.callbacks.manager import get_openai_callback

from app.agents.skills.base import BaseSkill, SkillResult
from app.domain.interfaces.vector_db import IVectorStoreProvider
from app.domain.interfaces.llm_provider import ILLMProvider


class AgricultureRAGSkill(BaseSkill):
    name = "Agriculture_Technical_Advice"
    description = (
        "Use this tool to answer questions about agriculture, soil environment, "
        "farming techniques, and water quality. Input is the user's question."
    )

    def __init__(
        self, vector_store_provider: IVectorStoreProvider, llm_provider: ILLMProvider
    ):
        """
        Initialize Agriculture RAG Skill with Dependency Injection.

        :param vector_store_provider: Implementation of IVectorStoreProvider
        :param llm_provider: Implementation of ILLMProvider
        """
        self.vector_store_provider = vector_store_provider
        self.llm_provider = llm_provider

        # Initialize Parent document Retriever (Đã tích hợp sẵn Cross-Encoder Reranker)
        logging.info(
            "Initializing Postgres Parent document Retriever (Vector + FTS + Reranker)..."
        )
        self.retriever = self.vector_store_provider.get_parent_document_retriever()

        # Khởi tạo Graph Provider cho Graph Path
        from app.infrastructure.vector_store.graph_provider import Neo4jGraphProvider
        self.graph_provider = Neo4jGraphProvider()

        # ==========================================
        # INTEGRATE ANTI-HALLUCINATION PROMPT
        # ==========================================
        self.llm = self.llm_provider.get_llm()

        system_prompt = """You are an expert in analyzing scientific documents. Your task is to answer the question STRICTLY BASED on the provided context.
            Mandatory rules:
            1. NO HALLUCINATION: Only use information present in the context. Do not add outside knowledge, do not explain or conclude if the context does not explicitly state it.
            2. EXACT DATA MATCHING (CRITICAL):
               - When the context lists items (e.g., A, B, C have values X, Y, Z respectively), YOU MUST match the exact object with its corresponding data. Absolutely do not swap data between objects.
               - Do not arbitrarily round numbers.
            3. HANDLING CONFLICTING DATA:
               - If the context has multiple different values for the same object in different paragraphs, prioritize extracting exactly according to the phrase/sentence containing that classification, or clearly state both if necessary. DO NOT arbitrarily merge data.
            4. ONLY EXTRACT AVAILABLE PROPOSALS: If the context mentions a solution/proposal, only state exactly what is written, do not invent more.
            5. HANDLING VAGUE/KEYWORD QUESTIONS: If the user's input is just a few short keywords (e.g., location name, crop name) instead of a clear question, summarize the most important information the context mentions about those keywords.
            6. HANDLING MISSING INFORMATION: If there is not enough information to answer, explicitly state: 'The context does not provide enough information on this issue.'
            7. FORMAT: The answer should be concise, structurally clear (statement -> specific cited data -> proposal if any).

            Context:
            {context}"""

        self.prompt_template = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                ("user", "{input}"),
            ]
        )

    def _load_all_docs_from_db(self) -> list[Document]:
        """Utility to get all chunks from DB to build BM25 Index."""
        print("Loading data from DB for BM25 Retriever...")
        try:
            # Get raw vector store to access PGVector internals
            vector_store = self.vector_store_provider.get_raw_vector_store()

            with vector_store._make_session() as session:
                records = session.query(vector_store.EmbeddingStore).all()
                print(f"DB query successful, loaded {len(records)} records for BM25.")
                return [
                    Document(page_content=r.document, metadata=r.cmetadata)
                    for r in records
                ]
        except Exception as e:
            print(f"Warning: Could not load data for BM25: {e}")
            return []

    def run(self, query: str, **kwargs) -> SkillResult:
        """
        Execute RAG Chain with Parallel Retrieval (Graph + Vector) and Context Merging.
        """
        agent_actions = []
        sources = []
        tokens_used = {"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0}

        try:
            agent_actions.append(f"Khởi chạy Parallel Retrieval cho câu hỏi: '{query[:50]}...'")

            # 1. Path 1: Graph Retrieval
            agent_actions.append("Đang truy vấn Knowledge Graph (Neo4j)...")
            graph_context = self.graph_provider.query_graph_context(query)
            if graph_context:
                agent_actions.append(f"Tìm thấy Graph Facts:\n{graph_context}")
            else:
                agent_actions.append("Không tìm thấy thông tin phù hợp trong Knowledge Graph.")

            # 2. Path 2: Vector Retrieval (PDR + Reranker)
            agent_actions.append("Đang truy vấn Vector DB (PostgreSQL)...")
            vector_docs = self.retriever.invoke(query)
            
            # Xử lý Vector Docs và Sources
            vector_context_parts = []
            for i, doc in enumerate(vector_docs):
                content = doc.page_content.replace("\n", " ")
                source_file = doc.metadata.get("source", "Unknown")
                file_id = doc.metadata.get("file_id") or doc.metadata.get("chunk_id", "N/A")
                
                vector_context_parts.append(f"[Document {i+1} | Source: {source_file}]: {content}")
                
                source_entry = {"file_id": file_id, "file_name": source_file}
                if source_entry not in sources:
                    sources.append(source_entry)
                    
            vector_context = "\n\n".join(vector_context_parts)
            agent_actions.append(f"Đã lấy được {len(vector_docs)} văn bản từ Vector DB.")

            # 3. Context Merging
            combined_context = "=== GRAPH FACTS ===\n" + (graph_context if graph_context else "None") + "\n\n"
            combined_context += "=== VECTOR TEXT ===\n" + (vector_context if vector_context else "None")

            # 4. LLM Synthesis
            agent_actions.append("Đang tổng hợp câu trả lời bằng LLM với Combined Context...")
            
            # Format prompt và invoke LLM
            prompt = self.prompt_template.format_messages(context=combined_context, input=query)
            
            with get_openai_callback() as cb:
                response = self.llm.invoke(prompt)
                
                tokens_used["total_tokens"] = cb.total_tokens
                tokens_used["prompt_tokens"] = cb.prompt_tokens
                tokens_used["completion_tokens"] = cb.completion_tokens

            answer = response.content
            agent_actions.append("Đã tạo câu trả lời thành công.")

            return SkillResult(
                answer=answer,
                skill_name=self.name,
                metadata={
                    "sources": sources,
                    "retrieved_docs_count": len(vector_docs),
                    "top_sources": sources[:3],
                },
                tokens_used=tokens_used,
                agent_actions=agent_actions,
            )

        except Exception as e:
            error_msg = f"Error during RAG execution: {e}"
            logging.error(error_msg, exc_info=True)
            return SkillResult(
                answer="Sorry, I encountered an error while searching the knowledge base.",
                skill_name=self.name,
                metadata={"error": str(e)},
                agent_actions=agent_actions + [error_msg],
            )
