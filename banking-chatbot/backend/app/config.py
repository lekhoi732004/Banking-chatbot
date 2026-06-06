"""
Application configuration for Banking Chatbot.
All settings are centralized here.
"""

import os
from pathlib import Path

# ============================================================
# Paths
# ============================================================
BASE_DIR = Path(__file__).resolve().parent.parent
KNOWLEDGE_BASE_DIR = BASE_DIR / "knowledge_base"
MOCK_DATA_DIR = BASE_DIR / "mock_data"
CHROMA_DB_DIR = BASE_DIR / "chroma_db"
FRONTEND_DIR = BASE_DIR.parent / "frontend"

# ============================================================
# Ollama / LLM Configuration
# ============================================================
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3:4b")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "bge-m3")

LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4096"))
LLM_REQUEST_TIMEOUT = int(os.getenv("LLM_REQUEST_TIMEOUT", "120"))

# ============================================================
# RAG Configuration
# ============================================================
RAG_CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "800"))
RAG_CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "200"))
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "5"))
CHROMA_COLLECTION_NAME = "banking_knowledge"

# ============================================================
# Session / Context Configuration
# ============================================================
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "1800"))  # 30 minutes
MAX_HISTORY_MESSAGES = int(os.getenv("MAX_HISTORY_MESSAGES", "20"))

# ============================================================
# External API Configuration
# ============================================================
VCB_EXCHANGE_RATE_URL = "https://portal.vietcombank.com.vn/Usercontrols/TVPortal.TyGia/pXML.aspx?b=1"
EXCHANGE_RATE_CACHE_TTL = int(os.getenv("EXCHANGE_RATE_CACHE_TTL", "300"))  # 5 minutes

# ============================================================
# Server Configuration
# ============================================================
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
