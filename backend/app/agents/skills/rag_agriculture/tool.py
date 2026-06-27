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

        # Initialize Parent document Retriever
        logging.info(
            "Initializing Postgres Parent document Retriever (Vector + FTS)..."
        )
        self.retriever = self.vector_store_provider.get_parent_document_retriever()

        # ==========================================
        # INTEGRATE ANTI-HALLUCINATION PROMPT
        # ==========================================
        llm = self.llm_provider.get_llm()

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

            Context: {context}"""

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                ("user", "{input}"),
            ]
        )

        # Initialize internal RAG Chain for this Skill
        document_qa_chain = create_stuff_documents_chain(llm, prompt)
        self.qa_chain = create_retrieval_chain(self.retriever, document_qa_chain)

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
        Execute RAG Chain and capture metadata (sources, tokens, actions).
        Only calls qa_chain once.
        """
        agent_actions = []
        tokens_used: Optional[Dict[str, int]] = None
        sources = []

        try:
            agent_actions.append(f"Invoking QA Chain for query: '{query[:50]}...'")

            # ===== STEP 1: INVOKE QA CHAIN (1 DB call) =====
            with get_openai_callback() as cb:
                result = self.qa_chain.invoke({"input": query})

                if cb.total_tokens > 0:
                    tokens_used = {
                        "prompt_tokens": cb.prompt_tokens,
                        "completion_tokens": cb.completion_tokens,
                        "total_tokens": cb.total_tokens,
                    }
                    agent_actions.append(
                        f"Consumed {cb.total_tokens} tokens from LLM "
                        f"(prompt: {cb.prompt_tokens}, completion: {cb.completion_tokens})"
                    )

            # ===== STEP 2: GET ANSWER AND DOCS FROM RESULT =====
            final_answer = result.get("answer", "No answer found.")
            retrieved_docs = result.get("context", [])

            agent_actions.append(
                f"Retrieved {len(retrieved_docs)} documents from vector store internally."
            )

            # ===== STEP 3: EXTRACT METADATA =====
            for idx, doc in enumerate(retrieved_docs[:5]):  # Top 5 docs
                metadata = doc.metadata or {}
                source_obj = {
                    "doc_index": idx,
                    "file_name": metadata.get("file_name", "Unknown"),
                    "hierarchy": metadata.get("document_hierarchy", "Unknown"),
                    "content_snippet": doc.page_content[:200],  # For UI
                    "full_content": doc.page_content,  # For Evaluation
                    "chunk_id": metadata.get("chunk_id", ""),
                }
                sources.append(source_obj)

            agent_actions.append("Answer generation and source extraction complete")

            # ===== STEP 4: RETURN SkillResult =====
            return SkillResult(
                answer=final_answer,
                skill_name=self.name,
                metadata={
                    "sources": sources,
                    "retrieved_docs_count": len(retrieved_docs),
                    "top_sources": sources[:3],
                },
                tokens_used=tokens_used,
                agent_actions=agent_actions,
            )

        except Exception as e:
            error_msg = f"[System retrieval error: {str(e)}]"
            import traceback

            agent_actions.append(f"Error occurred: {str(e)}")
            agent_actions.append(f"Traceback: {traceback.format_exc()[:100]}")
            return SkillResult(
                answer=error_msg,
                skill_name=self.name,
                metadata={
                    "sources": [],
                    "retrieved_docs_count": 0,
                    "top_sources": [],
                },
                tokens_used=tokens_used,
                agent_actions=agent_actions,
            )
