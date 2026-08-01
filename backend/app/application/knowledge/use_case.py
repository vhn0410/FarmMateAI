import json
from typing import AsyncGenerator
from app.schemas.chat_dto import ChatRequest
from app.domain.interfaces.llm_provider import ILLMProvider
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.output_parsers import StrOutputParser
from pydantic import BaseModel, Field
from app.infrastructure.vector_store.pgvector_provider import PGVectorProvider

class QueryFormulatorOutput(BaseModel):
    search_queries: list[str] = Field(description="List of exact search queries to look up in the database")


class KnowledgeChatUseCase:
    """
    Specialized use case for chat in the knowledge base.
    It does not store conversation history (stateless) to optimize speed and reduce database clutter.
    """

    def __init__(self, llm_provider: ILLMProvider):
        self.llm_provider = llm_provider

    async def stream_document_chat(
        self, request: ChatRequest, current_user, token: str = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat specifically for RAG over selected files (without an agent).
        """

        try:
            # 0. Formulate multiple search queries for better coverage
            yield f"data: {json.dumps({'event': 'status', 'message': 'Phân tích câu hỏi...'})}\n\n"
            llm_fast = self.llm_provider.get_llm()
            formulator_prompt = ChatPromptTemplate.from_messages([
                ("system", "You are an AI assistant. Rephrase the user's question into 1 to 3 distinct search queries to maximize retrieval of relevant documents from a vector database. Use Vietnamese. Return EXACTLY the JSON schema requested."),
                ("user", "Question: {question}")
            ])
            try:
                chain = formulator_prompt | llm_fast.with_structured_output(QueryFormulatorOutput)
                formulated = chain.invoke({"question": request.query})
                search_queries = formulated.search_queries
                if not search_queries:
                    search_queries = [request.query]
            except Exception as fe:
                print(f"Query formulation failed: {fe}. Falling back to raw query.")
                search_queries = [request.query]

            print(f"🔍 Formulated Queries: {search_queries}", flush=True)
            yield f"data: {json.dumps({'event': 'status', 'message': f'Tìm kiếm qua {len(search_queries)} hướng tiếp cận...'})}\n\n"

            # 1. Initialize retrievers with the file_ids filter
            file_ids = request.file_ids or []
            vector_provider = PGVectorProvider()
            retriever = vector_provider.get_parent_document_retriever(file_ids=file_ids)
            from app.infrastructure.vector_store.graph_provider import Neo4jGraphProvider
            graph_provider = Neo4jGraphProvider()

            # 2. Retrieve for all formulated queries and deduplicate
            all_docs = []
            all_graph_facts = []
            
            for q in search_queries:
                # Vector Search
                docs = retriever.invoke(q)
                all_docs.extend(docs)
                # Graph Search (Now supports file filtering)
                g_context = graph_provider.query_graph_context(q, file_ids=file_ids)
                if g_context:
                    # split facts by newline and add
                    all_graph_facts.extend([f.strip() for f in g_context.split('\n') if f.strip()])

            # Deduplicate documents by chunk_id
            unique_docs_dict = {}
            for doc in all_docs:
                cid = doc.metadata.get("chunk_id")
                if cid and cid not in unique_docs_dict:
                    unique_docs_dict[cid] = doc
                elif not cid:
                    # if no chunk_id, use content hash (simple fallback)
                    unique_docs_dict[hash(doc.page_content)] = doc
            final_docs = list(unique_docs_dict.values())
            
            # Deduplicate graph facts
            unique_graph_facts = list(dict.fromkeys(all_graph_facts))
            final_graph_context = "\n".join(unique_graph_facts)

            # Emit a loading signal along with the source list
            sources = []
            for i, doc in enumerate(final_docs):
                sources.append({
                    "id": i + 1,
                    "file_name": doc.metadata.get("file_name", ""),
                    "content_snippet": doc.page_content[:200],
                    "full_content": doc.page_content,
                    "chunk_id": doc.metadata.get("chunk_id", "")
                })
            
            if final_graph_context:
                sources.append({
                    "id": len(final_docs) + 1,
                    "file_name": "Knowledge Graph (Neo4j)",
                    "content_snippet": final_graph_context[:200],
                    "full_content": final_graph_context,
                    "chunk_id": "graph_nodes"
                })

            yield f"data: {json.dumps({'event': 'sources', 'sources': sources})}\n\n"
            yield f"data: {json.dumps({'event': 'status', 'message': 'Đang tổng hợp câu trả lời...'})}\n\n"

            # 3. Build a strict Anti-Hallucination RAG prompt with citations
            context_text = "\n\n".join([f"[Source {i+1}]:\n{doc.page_content}" for i, doc in enumerate(final_docs)])
            if final_graph_context:
                context_text = f"=== THÔNG TIN TỪ KNOWLEDGE GRAPH (Nguồn {len(final_docs) + 1}) ===\n{final_graph_context}\n\n=== THÔNG TIN TỪ TÀI LIỆU (Vector Search) ===\n{context_text}"
            
            system_prompt = (
                "You are FarmMate AI, an expert agricultural consultant. Your primary task is to answer the question based on the provided DOCUMENT SEGMENTS (Context) below.\n\n"
                "MANDATORY RULES:\n"
                "1. CITATIONS: You MUST cite the sources by inserting marker numbers such as [1], [2] at the end of every sentence or claim that uses information from the corresponding source.\n"
                "2. FALLBACK TO GENERAL KNOWLEDGE: If the provided context does not contain enough information to fully answer the question, you ARE ALLOWED to use your own expert agricultural knowledge to explain or supplement the answer. HOWEVER, you MUST wrap any information not found in the context with this exact warning format:\n"
                "⚠️ **[Khuyến nghị tham khảo từ kiến thức chung, không nằm trong tài liệu]**\n"
                "3. Always answer in Vietnamese.\n\n"
                f"CONTEXT:\n{context_text}"
            )
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", "{input}"),
            ])

            # 4. Create the chain with LCEL
            llm = self.llm_provider.get_llm()

            rag_chain = (
                {"input": RunnablePassthrough()}
                | prompt
                | llm
                | StrOutputParser()
            )

            bot_answer = ""

            # 4. Stream the result
            async for chunk in rag_chain.astream(request.query):
                if chunk:
                    bot_answer += chunk
                    yield f"data: {json.dumps({'event': 'token', 'text': chunk})}\n\n"

            # Return the completion signal (only echo back an existing session_id; do not create a fake one to avoid 404s in regular chat calls)
            done_payload = {'event': 'done', 'metadata': {}}
            if request.session_id:
                done_payload['session_id'] = request.session_id
            yield f"data: {json.dumps(done_payload)}\n\n"

        except Exception as e:
            print(f"Error in stream_document_chat: {str(e)}")
            yield f"data: {json.dumps({'event': 'error', 'message': str(e)})}\n\n"
