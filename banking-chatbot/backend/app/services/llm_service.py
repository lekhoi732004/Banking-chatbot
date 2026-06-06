"""
LLM Service — Manages Qwen3 and BGE-M3 models via Ollama.
Singleton pattern to avoid re-initialization.
"""

import logging
from typing import Optional

from langchain_ollama import ChatOllama, OllamaEmbeddings

from app.config import (
    EMBEDDING_MODEL,
    LLM_MAX_TOKENS,
    LLM_MODEL,
    LLM_REQUEST_TIMEOUT,
    LLM_TEMPERATURE,
    OLLAMA_BASE_URL,
)

logger = logging.getLogger(__name__)


class LLMService:
    """Singleton service for LLM and Embedding models."""

    _instance: Optional["LLMService"] = None
    _llm: Optional[ChatOllama] = None
    _embeddings: Optional[OllamaEmbeddings] = None

    def __new__(cls) -> "LLMService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_llm(self) -> ChatOllama:
        """Get or create the ChatOllama LLM instance."""
        if self._llm is None:
            logger.info(f"Initializing LLM: {LLM_MODEL} at {OLLAMA_BASE_URL}")
            self._llm = ChatOllama(
                model=LLM_MODEL,
                base_url=OLLAMA_BASE_URL,
                reasoning=True,
                temperature=LLM_TEMPERATURE,
                num_predict=LLM_MAX_TOKENS,
                request_timeout=LLM_REQUEST_TIMEOUT,
            )
            logger.info("LLM initialized successfully")
        return self._llm

    def get_embeddings(self) -> OllamaEmbeddings:
        """Get or create the OllamaEmbeddings instance."""
        if self._embeddings is None:
            logger.info(f"Initializing Embeddings: {EMBEDDING_MODEL} at {OLLAMA_BASE_URL}")
            self._embeddings = OllamaEmbeddings(
                model=EMBEDDING_MODEL,
                base_url=OLLAMA_BASE_URL,
            )
            logger.info("Embeddings initialized successfully")
        return self._embeddings


# Global singleton instance
llm_service = LLMService()


def get_llm() -> ChatOllama:
    """Convenience function to get the LLM."""
    return llm_service.get_llm()


def get_embeddings() -> OllamaEmbeddings:
    """Convenience function to get the embeddings model."""
    return llm_service.get_embeddings()
