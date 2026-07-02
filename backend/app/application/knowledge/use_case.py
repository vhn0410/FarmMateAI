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
    Use Case chuyên biệt cho Chat trong phần Knowledge Base.
    Không lưu trữ lịch sử trò chuyện (stateless) để tối ưu tốc độ và tránh rác Database.
    """

    def __init__(self, llm_provider: ILLMProvider):
        self.llm_provider = llm_provider

    async def stream_document_chat(
        self, request: ChatRequest, current_user, token: str = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat chuyên dụng cho RAG trên các file chỉ định (không dùng Agent).
        """

        try:
            # 1. Khởi tạo Retriever với bộ lọc file_ids
            file_ids = request.file_ids or []
            vector_provider = PGVectorProvider()
            retriever = vector_provider.get_parent_document_retriever(
                file_ids=file_ids)

            # 2. Tạo Prompt RAG chuẩn
            system_prompt = (
                "Bạn là một trợ lý ảo thông minh. Dựa vào các ĐOẠN TÀI LIỆU (Context) dưới đây, "
                "hãy trả lời câu hỏi của người dùng.\n"
                "Tuyệt đối KHÔNG BỊA ĐẶT THÔNG TIN. Nếu thông tin không có trong tài liệu, hãy trả lời là bạn không biết.\n\n"
                "CONTEXT:\n{context}"
            )
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", "{input}"),
            ])

            # 3. Tạo Chain bằng LCEL (tránh phụ thuộc vào thư viện langchain.chains)
            llm = self.llm_provider.get_llm()

            def get_docs(query: str):
                return retriever.invoke(query)

            def format_docs(docs):
                return "\n\n".join(doc.page_content for doc in docs)

            rag_chain = (
                {"context": RunnableLambda(
                    get_docs) | format_docs, "input": RunnablePassthrough()}
                | prompt
                | llm
                | StrOutputParser()
            )

            bot_answer = ""
            yield f"data: {json.dumps({'event': 'status', 'message': 'Đang tìm kiếm tài liệu...'})}\n\n"

            # 4. Stream kết quả
            async for chunk in rag_chain.astream(request.query):
                if chunk:
                    bot_answer += chunk
                    yield f"data: {json.dumps({'event': 'token', 'text': chunk})}\n\n"

            # Trả về tín hiệu kết thúc (chỉ trả về session_id cũ nếu có, không tạo session_id ảo để tránh lỗi 404 khi gọi luồng chat thường)
            done_payload = {'event': 'done', 'metadata': {}}
            if request.session_id:
                done_payload['session_id'] = request.session_id
            yield f"data: {json.dumps(done_payload)}\n\n"

        except Exception as e:
            print(f"Error in stream_document_chat: {str(e)}")
            yield f"data: {json.dumps({'event': 'error', 'message': str(e)})}\n\n"
