import json
from typing import AsyncGenerator
from app.schemas.chat_dto import ChatRequest
from app.domain.interfaces.llm_provider import ILLMProvider
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.output_parsers import StrOutputParser
from app.infrastructure.vector_store.pgvector_provider import PGVectorProvider


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
            # 1. Initialize the retriever with the file_ids filter
            file_ids = request.file_ids or []
            vector_provider = PGVectorProvider()
            retriever = vector_provider.get_parent_document_retriever(
                file_ids=file_ids)

            # 2. Retrieve docs first to send sources to the client
            docs = retriever.invoke(request.query)
            
            # Emit a loading signal along with the source list
            sources = []
            for i, doc in enumerate(docs):
                sources.append({
                    "id": i + 1,
                    "file_name": doc.metadata.get("file_name", ""),
                    "content_snippet": doc.page_content[:200],
                    "full_content": doc.page_content,
                    "chunk_id": doc.metadata.get("chunk_id", "")
                })
            yield f"data: {json.dumps({'event': 'sources', 'sources': sources})}\n\n"
            yield f"data: {json.dumps({'event': 'status', 'message': 'Searching documents...'})}\n\n"

            # 3. Build a standard RAG prompt with citations
            context_text = "\n\n".join([f"[Source {i+1}]:\n{doc.page_content}" for i, doc in enumerate(docs)])
            
            system_prompt = (
                "You are an intelligent virtual assistant. Based on the DOCUMENT SEGMENTS (Context) below, "
                "answer the user's question.\n"
                "Do NOT fabricate information. If the information is not in the documents, say that you do not know.\n"
                "IMPORTANT: Cite the sources by inserting marker numbers such as [1], [2] at the end of the sentence or paragraph that uses information from the corresponding source.\n\n"
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
