"""
Intent Classifier — Uses LLM to classify customer questions into intent categories.
Uses modern LCEL (LangChain Expression Language) — no deprecated APIs.
"""

import logging
import re
from typing import Optional

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from app.models.intents import IntentType, INTENT_DESCRIPTIONS
from app.services.llm_service import get_llm
from app.utils.prompt_templates import INTENT_CLASSIFICATION_PROMPT

logger = logging.getLogger(__name__)


class IntentClassifier:
    """Classifies user messages into predefined intent categories using LLM."""

    # Quick keyword matching for obvious intents (saves LLM calls)
    KEYWORD_RULES = {
        IntentType.TRA_CUU_TY_GIA: [
            "tỷ giá", "ty gia", "ngoại tệ", "ngoai te", "usd", "eur", "jpy",
            "gbp", "đô la", "do la", "euro", "yên", "yen", "quy đổi", "quy doi",
        ],
        IntentType.TRA_CUU_LAI_SUAT: [
            "lãi suất", "lai suat", "lãi xuất", "lai xuat",
        ],
        IntentType.TU_VAN_MO_TAI_KHOAN: [
            "mở tài khoản", "mo tai khoan", "mở tk", "mo tk",
            "đăng ký tài khoản", "dang ky tai khoan",
        ],
        IntentType.TU_VAN_THE_TIN_DUNG: [
            "thẻ tín dụng", "the tin dung", "thẻ visa", "the visa",
            "thẻ mastercard", "the mastercard", "credit card",
        ],
        IntentType.TU_VAN_VAY_VON: [
            "vay vốn", "vay von", "vay mua nhà", "vay mua nha",
            "vay mua xe", "vay tín chấp", "vay tin chap",
            "hồ sơ vay", "ho so vay", "thẩm định", "tham dinh",
        ],
        IntentType.TU_VAN_TIET_KIEM: [
            "tiết kiệm", "tiet kiem", "gửi tiết kiệm", "gui tiet kiem",
            "rút trước hạn", "rut truoc han",
        ],
        IntentType.TRA_CUU_BIEU_PHI: [
            "biểu phí", "bieu phi", "phí dịch vụ", "phi dich vu",
            "phí chuyển khoản", "phi chuyen khoan", "phí atm",
            "phí sms", "phi sms",
        ],
    }

    CHITCHAT_KEYWORDS = [
        "xin chào", "chào bạn", "hello", "hi ", "hey",
        "cảm ơn", "cam on", "thank",
        "tạm biệt", "tam biet", "bye",
        "bạn là ai", "ban la ai", "bạn tên gì", "ban ten gi",
        "khỏe không", "khoe khong",
    ]

    def __init__(self):
        self._chain = None

    async def classify(self, message: str, context: str = "") -> IntentType:
        """Classify a user message into an intent type.

        Args:
            message: The user's message text
            context: Conversation context string for disambiguation

        Returns:
            IntentType enum value
        """
        message_lower = message.lower().strip()

        # Step 1: Try keyword matching first (fast, no LLM call)
        # Skip keyword matching for calculation queries to let LLM classify them accurately
        if self._is_calculation_query(message_lower):
            logger.info("Calculation keywords/numbers detected. Skipping fast keyword matching to let LLM classify.")
            keyword_result = None
        else:
            keyword_result = self._keyword_match(message_lower)

        if keyword_result:
            logger.info(f"Intent classified by keywords: {keyword_result.value}")
            return keyword_result

        # Step 2: Use LLM for complex/ambiguous cases
        try:
            llm_result = await self._llm_classify(message, context)
            logger.info(f"Intent classified by LLM: {llm_result.value}")
            return llm_result
        except Exception as e:
            logger.error(f"LLM classification failed: {e}")
            return IntentType.CHITCHAT  # Fallback

    def _is_calculation_query(self, message_lower: str) -> bool:
        """Detect if the message is asking for a calculation (contains numbers/currencies and calculation-related keywords)."""
        # Currency/monetary amount patterns: e.g., 500 triệu, 100tr, 1 tỷ, 500.000.000, 100000000, etc.
        amount_patterns = [
            r"\d+\s*(triệu|tỷ|tr|ty|đ|vnd|vnds|usd|m)\b",
            r"\d{1,3}(\.\d{3}){2,}",  # numbers like 500.000.000
            r"\d{6,}",  # pure numbers >= 100,000
        ]
        
        has_amount = False
        for pattern in amount_patterns:
            if re.search(pattern, message_lower):
                has_amount = True
                break
                
        if not has_amount:
            # Also check for textual numbers like "mấy triệu", "bao nhiêu triệu", "vài trăm triệu"
            text_amount_patterns = [
                r"(mấy|bao nhiêu|vài)\s*(trăm|triệu|tỷ|tr|ty)\b",
                r"nợ bao nhiêu",
            ]
            for pattern in text_amount_patterns:
                if re.search(pattern, message_lower):
                    has_amount = True
                    break
        
        if not has_amount:
            return False
            
        # Calculation indicators
        calc_indicators = [
            "tính", "tinh", "bao nhiêu", "bao nhieu", "chu kỳ", "chu ky", "chu kì", "chu ki",
            "sau", "nhận", "nhan", "thu về", "thu ve", "mỗi tháng", "moi thang", "trả", "tra",
            "gốc", "goc", "lãi", "lai", "lịch trả", "lich tra", "dư nợ", "du no", "bao lau", "bao lâu"
        ]
        
        has_calc_indicator = False
        for indicator in calc_indicators:
            pattern = rf"\b{re.escape(indicator)}\b"
            if re.search(pattern, message_lower):
                has_calc_indicator = True
                break
                
        return has_calc_indicator

    def _keyword_match(self, message_lower: str) -> Optional[IntentType]:
        """Try to classify using keyword matching with word boundaries to prevent substring false positives."""
        # Check chitchat first
        for keyword in self.CHITCHAT_KEYWORDS:
            clean_kw = keyword.strip()
            pattern = rf"\b{re.escape(clean_kw)}\b"
            if re.search(pattern, message_lower):
                return IntentType.CHITCHAT

        # Check other intents
        for intent, keywords in self.KEYWORD_RULES.items():
            for keyword in keywords:
                clean_kw = keyword.strip()
                pattern = rf"\b{re.escape(clean_kw)}\b"
                if re.search(pattern, message_lower):
                    return intent

        return None  # No keyword match — need LLM

    async def _llm_classify(self, message: str, context: str = "") -> IntentType:
        """Use LLM to classify the intent."""
        prompt = ChatPromptTemplate.from_messages([
            ("system", INTENT_CLASSIFICATION_PROMPT),
        ])

        llm = get_llm()
        chain = prompt | llm | StrOutputParser()

        result = await chain.ainvoke({
            "context": context or "Chưa có ngữ cảnh trước đó",
            "question": message,
        })

        # Clean and parse the result
        return self._parse_intent(result)

    def _parse_intent(self, raw_result: str) -> IntentType:
        """Parse LLM output into IntentType enum."""
        # Clean up the result
        cleaned = raw_result.strip().lower()
        # Remove think tags
        cleaned = re.sub(r'<think>.*?</think>', '', cleaned, flags=re.DOTALL).strip()
        # Remove quotes, backticks, etc.
        cleaned = cleaned.strip('"\'`').strip()

        # Try exact match
        for intent in IntentType:
            if intent.value == cleaned:
                return intent

        # Try partial/fuzzy match
        for intent in IntentType:
            if intent.value in cleaned:
                return intent

        logger.warning(f"Could not parse intent from LLM output: '{raw_result}', defaulting to chitchat")
        return IntentType.CHITCHAT


# Global singleton
intent_classifier = IntentClassifier()
