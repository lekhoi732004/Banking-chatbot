"""
Orchestrator — Central dispatch logic for the Banking Chatbot.
Routes requests to appropriate handlers based on classified intent.
"""

import logging
from typing import Dict, Any

from app.core.context_manager import context_manager
from app.core.intent_classifier import intent_classifier
from app.core.response_generator import response_generator
from app.models.intents import IntentType, API_INTENTS, RAG_INTENTS
from app.models.schemas import ChatResponse
from app.services.exchange_rate_service import exchange_rate_service
from app.services.interest_rate_service import interest_rate_service
from app.services.rag_service import rag_service
from app.services.calculator_service import calculator_service

logger = logging.getLogger(__name__)

# Map intent types to human-readable topic names
INTENT_TOPIC_MAP = {
    IntentType.TU_VAN_MO_TAI_KHOAN: "mở tài khoản",
    IntentType.TU_VAN_THE_TIN_DUNG: "thẻ tín dụng",
    IntentType.TU_VAN_VAY_VON: "vay vốn",
    IntentType.TU_VAN_TIET_KIEM: "tiết kiệm",
    IntentType.TRA_CUU_BIEU_PHI: "biểu phí",
    IntentType.TRA_CUU_TY_GIA: "tỷ giá",
    IntentType.TRA_CUU_LAI_SUAT: "lãi suất",
    IntentType.TINH_TOAN_LAI_SUAT: "tính toán lãi suất",
    IntentType.CHITCHAT: "chào hỏi",
}


class Orchestrator:
    """Main orchestrator that coordinates intent classification, context, and response generation."""

    async def process_message(self, message: str, session_id: str) -> ChatResponse:
        """Process a user message and return a bot response.

        Args:
            message: User's message text
            session_id: Session identifier

        Returns:
            ChatResponse with bot response, detected intent, etc.
        """
        logger.info(f"Processing message from session {session_id}: {message[:100]}...")

        # Step 1: Load/create session context
        session = context_manager.get_or_create_session(session_id)

        # Step 2: Detect customer type from message
        detected_type = context_manager.detect_customer_type(message)
        if detected_type:
            context_manager.update_customer_type(session_id, detected_type)

        # Step 3: Classify intent
        context_summary = context_manager.get_context_summary(session_id)
        intent = await intent_classifier.classify(message, context_summary)
        logger.info(f"Detected intent: {intent.value}")

        # Step 3.5: Context preservation for follow-up questions
        if intent == IntentType.CHITCHAT and session.current_topic:
            TOPIC_INTENT_MAP = {
                "mở tài khoản": IntentType.TU_VAN_MO_TAI_KHOAN,
                "thẻ tín dụng": IntentType.TU_VAN_THE_TIN_DUNG,
                "vay vốn": IntentType.TU_VAN_VAY_VON,
                "tiết kiệm": IntentType.TU_VAN_TIET_KIEM,
                "biểu phí": IntentType.TRA_CUU_BIEU_PHI,
                "tỷ giá": IntentType.TRA_CUU_TY_GIA,
                "lãi suất": IntentType.TRA_CUU_LAI_SUAT,
                "tính toán lãi suất": IntentType.TINH_TOAN_LAI_SUAT,
            }
            active_intent = TOPIC_INTENT_MAP.get(session.current_topic)
            if active_intent:
                message_lower = message.lower().strip()
                is_real_chitchat = False
                for kw in intent_classifier.CHITCHAT_KEYWORDS:
                    if kw in message_lower:
                        is_real_chitchat = True
                        break
                if not is_real_chitchat:
                    logger.info(f"Overriding chitchat intent with active topic intent: {active_intent.value} (follow-up detected)")
                    intent = active_intent

        # Step 4: Update topic
        topic = INTENT_TOPIC_MAP.get(intent, "")
        if topic and intent != IntentType.CHITCHAT:
            context_manager.update_topic(session_id, topic)

        # Step 5: Add user message to history
        context_manager.add_message(session_id, "user", message)

        # Step 6: Get chat history for context
        chat_history = context_manager.get_formatted_history(session_id)

        # Step 7: Dispatch to appropriate handler
        try:
            if intent == IntentType.CHITCHAT:
                bot_response = await self._handle_chitchat(message, chat_history)
            elif intent == IntentType.TINH_TOAN_LAI_SUAT:
                bot_response = await self._handle_calculator_query(message, chat_history)
            elif intent in API_INTENTS:
                bot_response = await self._handle_api_query(intent, message, chat_history)
            elif intent in RAG_INTENTS:
                bot_response = await self._handle_rag_query(
                    intent, message, session, chat_history
                )
            else:
                bot_response = await self._handle_chitchat(message, chat_history)
        except Exception as e:
            logger.error(f"Error handling intent {intent.value}: {e}", exc_info=True)
            bot_response = (
                "Xin lỗi anh/chị, hệ thống đang gặp sự cố. "
                "Vui lòng thử lại sau hoặc liên hệ hotline 1900-xxxx ạ."
            )

        # Step 8: Add bot response to history
        context_manager.add_message(session_id, "assistant", bot_response)

        # Step 9: Build response
        return ChatResponse(
            response=bot_response,
            intent=intent.value,
            session_id=session_id,
            metadata={
                "customer_type": session.customer_type,
                "current_topic": session.current_topic,
                "topic_stack": session.topic_stack,
            },
        )

    async def _handle_chitchat(self, message: str, chat_history: str) -> str:
        """Handle chitchat/small talk messages."""
        return await response_generator.generate_chitchat_response(message, chat_history)

    async def _handle_calculator_query(self, message: str, chat_history: str) -> str:
        """Handle calculation queries (savings interest or loan repayment)."""
        return await calculator_service.calculate(message, chat_history)

    async def _handle_api_query(
        self, intent: IntentType, message: str, chat_history: str
    ) -> str:
        """Handle API-based queries (exchange rate, interest rate)."""
        if intent == IntentType.TRA_CUU_TY_GIA:
            rates_response = await exchange_rate_service.get_rates()
            api_data = exchange_rate_service.format_rates_for_llm(rates_response)
        elif intent == IntentType.TRA_CUU_LAI_SUAT:
            api_data = interest_rate_service.format_rates_for_llm()
        else:
            api_data = "Không có dữ liệu."

        return await response_generator.generate_api_response(
            question=message,
            api_data=api_data,
            chat_history=chat_history,
        )

    async def _handle_rag_query(
        self, intent: IntentType, message: str, session, chat_history: str
    ) -> str:
        """Handle knowledge base queries using RAG."""
        customer_type = "cá nhân" if session.customer_type == "ca_nhan" else "doanh nghiệp"
        current_topic = INTENT_TOPIC_MAP.get(intent, "")

        return await rag_service.query(
            question=message,
            customer_type=customer_type,
            current_topic=current_topic,
            chat_history=chat_history,
        )


# Global singleton
orchestrator = Orchestrator()
