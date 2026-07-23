"""
Helper module to generate suggested questions, extract sources, and aggregate tokens.
Handles the logic to populate ChatResponse fields from SkillResult.
"""

from typing import List, Dict, Any, Optional
from app.schemas.chat_dto import SourceDocument, TokenUsage
from app.domain.interfaces.llm_provider import ILLMProvider


class ResponseEnhancer:
    """
    Enhances a SkillResult into a fully populated ChatResponse.
    """

    @staticmethod
    def extract_sources(
        skill_result_metadata: Dict[str, Any],
        answer: str,
        skill_name: str = "",
    ) -> List[SourceDocument]:
        """
        Extract sources from SkillResult metadata.
        Performs citation matching: keep only sources referenced in the answer.

        :param skill_result_metadata: metadata dict from SkillResult
        :param answer: answer returned by the skill
        :param skill_name: skill name used for logging
        :return: list of relevant SourceDocument entries
        """
        sources_raw = skill_result_metadata.get("sources", [])
        if not sources_raw:
            return []

        source_documents = []

        # ===== CITATION MATCHING LOGIC =====
        # Simple keyword matching: keep the source if its content appears in the answer
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

            # Check whether any source keywords appear in the answer
            is_cited = False
            for keyword in keywords:
                keyword_clean = keyword.strip().lower()
                if len(keyword_clean) > 3 and keyword_clean in answer_lower:
                    is_cited = True
                    break

            # If the answer mentions the file_name or hierarchy, keep this source
            if is_cited:
                source_documents.append(
                    SourceDocument(
                        file_name=file_name,
                        hierarchy=hierarchy,
                        content_snippet=content_snippet,
                    )
                )

        # If no matches are found, return the top 3 sources as a fallback
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
        Generate suggested follow-up questions based on the answer.
        Uses an LLM to produce natural questions.

        :param answer: primary answer returned by the skill
        :param query: original user query
        :param sources: list of sources used
        :param llm_provider: LLM provider used to generate questions
        :return: list of suggested questions (up to 3)
        """

        try:
            llm = llm_provider.get_llm()

            # Build context string from sources
            sources_context = ""
            if sources:
                sources_context = "\n".join(
                    [f"- {s.file_name} ({s.hierarchy})" for s in sources[:3]]
                )

            # Prompt to generate questions
            prompt = f"""Based on the original question and answer below, generate 3 natural and relevant follow-up questions.

Original question: {query}

Answer: {answer}

Reference sources:
{sources_context}

Generate 3 questions the user might ask next. Put each question on its own line, starting with "-". Example:
- Question 1?
- Question 2?
- Question 3?

Return only 3 questions and nothing else."""

            # Call LLM
            response = llm.invoke(prompt)
            response_text = (
                response.content if hasattr(response, "content") else str(response)
            )

            # Parse questions from the response (each line starts with -)
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
                "Could you explain this in more detail?",
                "Are there other ways to address this issue?",
                "Is this a common problem?",
            ]

    @staticmethod
    def aggregate_tokens(
        skill_tokens: Optional[Dict[str, int]] = None,
        suggested_questions_tokens: Optional[Dict[str, int]] = None,
    ) -> Optional[TokenUsage]:
        """
        Aggregate token usage from all LLM calls.

        :param skill_tokens: token usage from the skill (RAG, Weather, etc.)
        :param suggested_questions_tokens: token usage from suggested questions generation
        :return: TokenUsage object with the total tokens
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
