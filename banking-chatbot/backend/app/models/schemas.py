"""
Pydantic schemas for API request/response models.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ============================================================
# Chat Models
# ============================================================

class ChatRequest(BaseModel):
    """HTTP chat request body."""
    message: str = Field(..., min_length=1, max_length=2000, description="User message")
    session_id: str = Field(..., description="Session identifier")


class ChatResponse(BaseModel):
    """HTTP chat response body."""
    response: str = Field(..., description="Bot response text")
    intent: str = Field(..., description="Detected intent")
    session_id: str = Field(..., description="Session identifier")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    metadata: Optional[Dict[str, Any]] = None


# ============================================================
# WebSocket Models
# ============================================================

class WSMessage(BaseModel):
    """WebSocket message format."""
    type: str = Field(default="message", description="Message type: message, typing, error, system")
    content: str = Field(default="", description="Message content")
    sender: str = Field(default="user", description="Sender: user or bot")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    metadata: Optional[Dict[str, Any]] = None


# ============================================================
# Intent Classification
# ============================================================

class IntentResult(BaseModel):
    """Result from intent classification."""
    intent: str = Field(..., description="Classified intent type")
    confidence: float = Field(default=0.0, ge=0, le=1, description="Confidence score")
    entities: Dict[str, Any] = Field(default_factory=dict, description="Extracted entities")


# ============================================================
# Session / Context
# ============================================================

class SessionContext(BaseModel):
    """Session context for a customer conversation."""
    session_id: str
    customer_type: str = Field(default="ca_nhan", description="ca_nhan or doanh_nghiep")
    current_topic: Optional[str] = None
    topic_stack: List[str] = Field(default_factory=list)
    entities: Dict[str, Any] = Field(default_factory=dict)
    conversation_summary: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    last_active: str = Field(default_factory=lambda: datetime.now().isoformat())


# ============================================================
# Exchange Rate
# ============================================================

class ExchangeRate(BaseModel):
    """Exchange rate for a currency pair."""
    currency_code: str
    currency_name: str
    buy_cash: Optional[float] = None
    buy_transfer: Optional[float] = None
    sell: Optional[float] = None


class ExchangeRateResponse(BaseModel):
    """Response containing exchange rates."""
    rates: List[ExchangeRate]
    updated_at: str
    source: str = "Vietcombank"
    cached: bool = False


# ============================================================
# Interest Rate
# ============================================================

class InterestRateResponse(BaseModel):
    """Response containing interest rates."""
    data: Dict[str, Any]
    updated_at: str
    source: str = "VietBank (tham khảo)"
