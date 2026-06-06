"""
Context Manager — Manages conversation sessions, memory, and topic tracking.
Uses in-memory storage with TTL-based cleanup.
"""

import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from langchain_core.chat_history import BaseChatMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.messages import AIMessage, HumanMessage

from app.config import MAX_HISTORY_MESSAGES, SESSION_TTL_SECONDS
from app.models.schemas import SessionContext

logger = logging.getLogger(__name__)


class ContextManager:
    """Manages conversation context, session data, and message history."""

    def __init__(self):
        # session_id -> SessionContext
        self._sessions: Dict[str, SessionContext] = {}
        # session_id -> ChatMessageHistory
        self._histories: Dict[str, ChatMessageHistory] = {}
        # session_id -> last_access_timestamp
        self._last_access: Dict[str, float] = {}

    def get_or_create_session(self, session_id: str) -> SessionContext:
        """Get existing session or create a new one."""
        self._cleanup_expired()

        if session_id not in self._sessions:
            logger.info(f"Creating new session: {session_id}")
            self._sessions[session_id] = SessionContext(session_id=session_id)
            self._histories[session_id] = ChatMessageHistory()

        self._last_access[session_id] = time.time()
        self._sessions[session_id].last_active = datetime.now().isoformat()
        return self._sessions[session_id]

    def get_message_history(self, session_id: str) -> ChatMessageHistory:
        """Get the chat message history for a session."""
        if session_id not in self._histories:
            self._histories[session_id] = ChatMessageHistory()
        return self._histories[session_id]

    def add_message(self, session_id: str, role: str, content: str):
        """Add a message to the session history.

        Args:
            session_id: Session identifier
            role: 'user' or 'assistant'
            content: Message content
        """
        history = self.get_message_history(session_id)

        if role == "user":
            history.add_user_message(content)
        else:
            history.add_ai_message(content)

        # Trim history if too long
        if len(history.messages) > MAX_HISTORY_MESSAGES:
            history.messages = history.messages[-MAX_HISTORY_MESSAGES:]

        self._last_access[session_id] = time.time()

    def update_topic(self, session_id: str, new_topic: str):
        """Update the current topic for a session.

        Handles topic stack: push new topic, pop back to previous.
        """
        session = self.get_or_create_session(session_id)

        if session.current_topic and session.current_topic != new_topic:
            # Push current topic to stack (if not already there)
            if session.current_topic not in session.topic_stack:
                session.topic_stack.append(session.current_topic)

            # Keep stack manageable
            if len(session.topic_stack) > 5:
                session.topic_stack = session.topic_stack[-5:]

        session.current_topic = new_topic
        logger.debug(f"Session {session_id}: topic={new_topic}, stack={session.topic_stack}")

    def update_entities(self, session_id: str, entities: Dict):
        """Merge new entities into session context."""
        session = self.get_or_create_session(session_id)
        session.entities.update(entities)

    def update_customer_type(self, session_id: str, customer_type: str):
        """Update customer type (ca_nhan or doanh_nghiep)."""
        session = self.get_or_create_session(session_id)
        if customer_type in ("ca_nhan", "doanh_nghiep"):
            session.customer_type = customer_type
            logger.info(f"Session {session_id}: customer_type updated to {customer_type}")

    def get_formatted_history(self, session_id: str, max_messages: int = 10) -> str:
        """Get formatted chat history as a string for prompt context."""
        history = self.get_message_history(session_id)
        messages = history.messages[-max_messages:] if history.messages else []

        if not messages:
            return "Chưa có lịch sử hội thoại."

        lines = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                lines.append(f"Khách hàng: {msg.content}")
            elif isinstance(msg, AIMessage):
                # Truncate long bot responses in history
                content = msg.content[:200] + "..." if len(msg.content) > 200 else msg.content
                lines.append(f"Trợ lý: {content}")

        return "\n".join(lines)

    def get_context_summary(self, session_id: str) -> str:
        """Get a summary of the current session context for intent classification."""
        session = self.get_or_create_session(session_id)
        parts = []

        if session.current_topic:
            parts.append(f"Chủ đề hiện tại: {session.current_topic}")
        if session.customer_type:
            parts.append(f"Loại khách hàng: {session.customer_type}")
        if session.entities:
            entities_str = ", ".join(f"{k}: {v}" for k, v in session.entities.items())
            parts.append(f"Thông tin đã biết: {entities_str}")
        if session.topic_stack:
            parts.append(f"Các chủ đề trước: {', '.join(session.topic_stack)}")

        return "\n".join(parts) if parts else "Chưa có ngữ cảnh trước đó"

    def detect_customer_type(self, message: str) -> Optional[str]:
        """Try to detect customer type from message content."""
        message_lower = message.lower()

        business_keywords = [
            "doanh nghiệp", "công ty", "cong ty", "pháp nhân", "phap nhan",
            "hộ kinh doanh", "ho kinh doanh",
        ]
        personal_keywords = [
            "cá nhân", "ca nhan", "tôi muốn", "toi muon", "mình muốn", "minh muon",
        ]

        for kw in business_keywords:
            if kw in message_lower:
                return "doanh_nghiep"

        for kw in personal_keywords:
            if kw in message_lower:
                return "ca_nhan"

        return None

    def _cleanup_expired(self):
        """Remove expired sessions based on TTL."""
        now = time.time()
        expired = [
            sid for sid, ts in self._last_access.items()
            if (now - ts) > SESSION_TTL_SECONDS
        ]
        for sid in expired:
            logger.info(f"Cleaning up expired session: {sid}")
            self._sessions.pop(sid, None)
            self._histories.pop(sid, None)
            self._last_access.pop(sid, None)

    def get_active_sessions_count(self) -> int:
        """Get the number of active sessions."""
        self._cleanup_expired()
        return len(self._sessions)


# Global singleton
context_manager = ContextManager()
