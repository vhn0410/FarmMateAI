"""
Helper module để generate suggested questions, extract sources, và aggregate tokens.
Xử lý logic để populate các field trong ChatResponse từ SkillResult.
"""
from typing import List, Dict, Any, Optional
from app.schemas.chat_dto import SourceDocument, TokenUsage
from app.domain.interfaces.llm_provider import ILLMProvider
import re


class ResponseEnhancer:
    """
    Xử lý logic tăng cường response từ SkillResult thành ChatResponse đầy đủ thông tin.
    """

    @staticmethod
    def extract_sources(
        skill_result_metadata: Dict[str, Any],
        answer: str,
        skill_name: str = "",
    ) -> List[SourceDocument]:
        """
        Trích xuất sources từ metadata của SkillResult.
        Thực hiện citation matching: chỉ giữ sources mà được referenced trong answer.

        :param skill_result_metadata: metadata dict từ SkillResult
        :param answer: Câu trả lời từ skill
        :param skill_name: Tên skill để log
        :return: Danh sách SourceDocument có liên quan
        """
        sources_raw = skill_result_metadata.get("sources", [])
        if not sources_raw:
            return []

        source_documents = []

        # ===== CITATION MATCHING LOGIC =====
        # Đơn giản: keyword match - nếu content từ source xuất hiện trong answer thì keep
        answer_lower = answer.lower()

        for source in sources_raw:
            file_name = source.get("file_name", "")
            hierarchy = source.get("hierarchy", "")
            content_snippet = source.get("content_snippet", "")

            # Keyword matching: check if key terms from source appear in answer
            keywords = []
            if hierarchy:
                keywords.extend(hierarchy.split(">"))
            if file_name:
                keywords.append(file_name)

            # Kiểm tra xem có keyword nào từ source xuất hiện trong answer không
            is_cited = False
            for keyword in keywords:
                keyword_clean = keyword.strip().lower()
                if len(keyword_clean) > 3 and keyword_clean in answer_lower:
                    is_cited = True
                    break

            # Nếu answer mention file_name hay hierarchy, giữ lại source này
            if is_cited:
                source_documents.append(
                    SourceDocument(
                        file_name=file_name,
                        hierarchy=hierarchy,
                        content_snippet=content_snippet,
                    )
                )

        # Nếu không có match nào, return top 3 sources as fallback
        if not source_documents and sources_raw:
            for source in sources_raw[:3]:
                source_documents.append(
                    SourceDocument(
                        file_name=source.get("file_name", ""),
                        hierarchy=source.get("hierarchy", ""),
                        content_snippet=source.get("content_snippet", ""),
                    )
                )

        return source_documents

    @staticmethod
    async def generate_suggested_questions(
        answer: str,
        query: str,
        sources: List[SourceDocument],
        llm_provider: Optional[ILLMProvider] = None,
    ) -> List[str]:
        """
        Generate suggested follow-up questions dựa trên answer.
        Sử dụng LLM để sinh ra questions tự nhiên.

        :param answer: Câu trả lời chính từ skill
        :param query: Câu hỏi gốc từ user
        :param sources: Danh sách sources được sử dụng
        :param llm_provider: LLM provider để generate questions
        :return: Danh sách suggested questions (up to 3)
        """
        
        try:
            llm = llm_provider.get_llm()

            # Build context string from sources
            sources_context = ""
            if sources:
                sources_context = "\n".join(
                    [f"- {s.file_name} ({s.hierarchy})" for s in sources[:3]]
                )

            # Prompt để generate questions
            prompt = f"""Dựa trên câu hỏi gốc và câu trả lời dưới đây, hãy sinh ra 3 câu hỏi follow-up tự nhiên và liên quan.

Câu hỏi gốc: {query}

Câu trả lời: {answer}

Nguồn tham khảo:
{sources_context}

Hãy sinh ra 3 câu hỏi mà người dùng có thể hỏi tiếp. Mỗi câu hỏi trên một dòng, bắt đầu bằng "-". Ví dụ:
- Câu hỏi 1?
- Câu hỏi 2?
- Câu hỏi 3?

Chỉ trả về 3 câu hỏi, không thêm gì khác."""

            # Call LLM
            response = llm.invoke(prompt)
            response_text = (
                response.content if hasattr(response, "content") else str(response)
            )

            # Parse questions từ response (mỗi dòng bắt đầu với -)
            questions = []
            for line in response_text.split("\n"):
                line = line.strip()
                if line.startswith("-"):
                    question = line[1:].strip()
                    if question:
                        questions.append(question)

            return questions[:3]  # Max 3 questions

        except Exception as e:
            print(f"Error generating suggested questions: {e}")
            # Fallback: return generic questions
            return [
                "Bạn có thể giải thích thêm chi tiết về điều này không?",
                "Có các phương pháp khác để giải quyết vấn đề này không?",
                "Đây có phải là vấn đề phổ biến không?",
            ]

    @staticmethod
    def aggregate_tokens(
        skill_tokens: Optional[Dict[str, int]] = None,
        suggested_questions_tokens: Optional[Dict[str, int]] = None,
    ) -> Optional[TokenUsage]:
        """
        Aggregate token usage từ tất cả LLM calls.

        :param skill_tokens: Token usage từ skill (RAG, Weather, etc.)
        :param suggested_questions_tokens: Token usage từ suggested questions generation
        :return: TokenUsage object với tổng tokens
        """
        total_prompt = 0
        total_completion = 0
        total_tokens = 0

        if skill_tokens:
            total_prompt += skill_tokens.get("prompt_tokens", 0)
            total_completion += skill_tokens.get("completion_tokens", 0)
            total_tokens += skill_tokens.get("total_tokens", 0)

        if suggested_questions_tokens:
            total_prompt += suggested_questions_tokens.get("prompt_tokens", 0)
            total_completion += suggested_questions_tokens.get("completion_tokens", 0)
            total_tokens += suggested_questions_tokens.get("total_tokens", 0)

        if total_tokens == 0:
            return None

        return TokenUsage(
            prompt_tokens=total_prompt,
            completion_tokens=total_completion,
            total_tokens=total_tokens,
        )
