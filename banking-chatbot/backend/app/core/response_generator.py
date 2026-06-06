"""
Response Generator — Formats final responses using LLM.
Handles API data formatting and chitchat responses.
"""

import logging
import re

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from app.services.llm_service import get_llm
from app.utils.prompt_templates import (
    API_DATA_RESPONSE_PROMPT,
    CHITCHAT_RESPONSE_PROMPT,
)

logger = logging.getLogger(__name__)


class ResponseGenerator:
    """Generates natural language responses from data or chitchat context."""

    async def generate_api_response(
        self,
        question: str,
        api_data: str,
        chat_history: str = "",
    ) -> str:
        """Generate a response using API data.

        Args:
            question: User's question
            api_data: Formatted API data string
            chat_history: Conversation history

        Returns:
            Natural language response
        """
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", API_DATA_RESPONSE_PROMPT),
                ("human", "{question}"),
            ])

            llm = get_llm()
            chain = prompt | llm | StrOutputParser()

            result = await chain.ainvoke({
                "api_data": api_data,
                "chat_history": chat_history or "Chưa có lịch sử",
                "question": question,
            })

            cleaned = self._clean_response(result)
            if cleaned:
                return cleaned

            logger.warning("API response generation returned empty text; using raw data fallback")
            return f"Dạ, em có dữ liệu cho anh/chị đây ạ:\n\n{api_data}"

        except Exception as e:
            logger.error(f"API response generation failed: {e}")
            return f"Dạ, em có dữ liệu cho anh/chị đây ạ:\n\n{api_data}"

    async def generate_chitchat_response(
        self,
        question: str,
        chat_history: str = "",
    ) -> str:
        """Generate a chitchat response.

        Args:
            question: User's message
            chat_history: Conversation history

        Returns:
            Friendly response
        """
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", CHITCHAT_RESPONSE_PROMPT),
                ("human", "{question}"),
            ])

            llm = get_llm()
            chain = prompt | llm | StrOutputParser()

            result = await chain.ainvoke({
                "chat_history": chat_history or "Chưa có lịch sử",
                "question": question,
            })

            cleaned = self._clean_response(result)
            if cleaned:
                return cleaned

            logger.warning("Chitchat response generation returned empty text; using fallback")
            return (
                "Xin chào anh/chị! 👋 Em là trợ lý ảo VietBank. "
                "Em có thể hỗ trợ anh/chị về tỷ giá, lãi suất, mở tài khoản, "
                "thẻ tín dụng, vay vốn và nhiều dịch vụ khác ạ!"
            )

        except Exception as e:
            logger.error(f"Chitchat response generation failed: {e}")
            return (
                "Xin chào anh/chị! 👋 Em là trợ lý ảo VietBank. "
                "Em có thể hỗ trợ anh/chị về tỷ giá, lãi suất, mở tài khoản, "
                "thẻ tín dụng, vay vốn và nhiều dịch vụ khác ạ!"
            )

    @staticmethod
    def _clean_response(text: str) -> str:
        """Clean LLM response by removing thinking tags and unwanted artifacts."""
        # Remove <think>...</think> blocks
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        # Qwen3 may print reasoning in plain text and then mark the final answer.
        for marker in ("...done thinking.", "done thinking."):
            marker_index = text.lower().rfind(marker)
            if marker_index != -1:
                text = text[marker_index + len(marker):]
                break
        # Remove /no_think tags
        text = text.replace('/no_think', '').replace('/think', '')
        
        # Detect and strip common transition markers
        for marker in (
            "let me draft the response:",
            "here is the response:",
            "drafted response:",
            "response in vietnamese:",
            "here is the draft:"
        ):
            idx = text.lower().find(marker)
            if idx != -1:
                text = text[idx + len(marker):].strip()
                break

        # Remove excessive whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = text.strip()

        # Split into paragraphs and strip English reasoning paragraphs from the beginning
        paragraphs = text.split('\n\n')
        cleaned_paragraphs = []
        in_reasoning = True
        
        reasoning_indicators = (
            "tackle this query",
            "customer is asking",
            "first, i need to",
            "the rules say",
            "let me structure",
            "let me draft",
            "user's question",
            "original data",
            "so the response should",
            "i need to make sure",
        )
        english_stopwords = {"the", "and", "to", "of", "is", "in", "that", "it", "for", "on", "are", "as", "with", "at", "by", "an", "be", "this", "have", "from", "i", "need", "should", "query", "customer", "user", "response", "we", "can", "will"}

        for p in paragraphs:
            p_strip = p.strip()
            if not p_strip:
                continue
                
            if in_reasoning:
                p_lower = p_strip.lower()
                # Check indicator
                if any(indicator in p_lower for indicator in reasoning_indicators):
                    continue
                
                # Check word count
                words = [w.strip(".,?!:;()[]{}*\"'-") for w in p_lower.split()]
                words = [w for w in words if w]
                if words:
                    english_word_count = sum(1 for w in words if w in english_stopwords)
                    accented_word_count = sum(1 for w in words if any(c in w for c in "áàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵđĐ"))
                    if english_word_count >= 3 and accented_word_count <= 2:
                        continue
                in_reasoning = False
                
            cleaned_paragraphs.append(p)
            
        text = '\n\n'.join(cleaned_paragraphs)
        text = text.strip()

        reasoning_prefixes = (
            "thinking",
            "okay,",
            "ok,",
            "alright",
            "let me",
            "let's",
            "first,",
            "the user",
        )
        
        # Strip matching prefixes from the beginning of the text
        text_lower = text.lower()
        has_changed = True
        while has_changed:
            has_changed = False
            for prefix in reasoning_prefixes:
                if text_lower.startswith(prefix):
                    text = text[len(prefix):].strip()
                    text_lower = text.lower()
                    has_changed = True
                    break

        return text


# Global singleton
response_generator = ResponseGenerator()
