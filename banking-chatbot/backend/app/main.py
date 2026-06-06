"""
FastAPI application entry point for the Banking Chatbot.
Provides WebSocket chat, REST API endpoints, and serves the frontend.
"""

import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.config import FRONTEND_DIR
from app.core.context_manager import context_manager
from app.core.orchestrator import orchestrator
from app.models.schemas import ChatRequest, ChatResponse, WSMessage
from app.services.exchange_rate_service import exchange_rate_service
from app.services.interest_rate_service import interest_rate_service
from app.services.rag_service import rag_service

# ============================================================
# Logging Setup
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ============================================================
# App Lifespan
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    logger.info("=" * 60)
    logger.info("VietBank AI Chatbot — Starting up...")
    logger.info("=" * 60)

    # Initialize RAG (load/index documents)
    try:
        rag_service.get_vectorstore()
        logger.info("RAG pipeline initialized")
    except Exception as e:
        logger.warning(f"RAG initialization warning: {e}")

    # Preload interest rate data
    try:
        interest_rate_service.get_all_rates()
        logger.info("Interest rate data loaded")
    except Exception as e:
        logger.warning(f"Interest rate loading warning: {e}")

    logger.info("=" * 60)
    logger.info("Server ready! Open http://localhost:8000 in your browser")
    logger.info("=" * 60)

    yield

    logger.info("Shutting down VietBank AI Chatbot...")


# ============================================================
# FastAPI App
# ============================================================
app = FastAPI(
    title="VietBank AI Chatbot",
    description="Trợ lý ảo tư vấn khách hàng cá nhân ngân hàng",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# WebSocket Chat Endpoint
# ============================================================
@app.websocket("/ws/chat/{session_id}")
async def websocket_chat(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time chat."""
    await websocket.accept()
    logger.info(f"WebSocket connected: session={session_id}")

    # Send welcome message
    welcome = WSMessage(
        type="welcome",
        content=(
            "Xin chào anh/chị! 👋 Em là trợ lý ảo **VietBank AI**.\n\n"
            "Em có thể hỗ trợ anh/chị về:\n"
            "• 💱 Tỷ giá ngoại tệ (real-time)\n"
            "• 💰 Lãi suất tiết kiệm & cho vay\n"
            "• 🏦 Thủ tục mở tài khoản\n"
            "• 💳 Thẻ tín dụng\n"
            "• 🏠 Vay vốn mua nhà, mua xe\n"
            "• 📋 Biểu phí dịch vụ\n\n"
            "Anh/chị cần em hỗ trợ gì ạ? 😊"
        ),
        sender="bot",
        timestamp=datetime.now().isoformat(),
    )
    await websocket.send_text(welcome.model_dump_json())

    try:
        while True:
            # Receive message
            data = await websocket.receive_text()

            try:
                # Try parsing as JSON
                msg_data = json.loads(data)
                user_message = msg_data.get("content", msg_data.get("message", data))
            except json.JSONDecodeError:
                user_message = data

            user_message = user_message.strip()
            if not user_message:
                continue

            logger.info(f"[{session_id}] User: {user_message[:80]}...")

            # Send typing indicator
            typing_msg = WSMessage(type="typing", sender="bot")
            await websocket.send_text(typing_msg.model_dump_json())

            # Process message
            try:
                response = await orchestrator.process_message(user_message, session_id)

                # Send bot response
                bot_msg = WSMessage(
                    type="message",
                    content=response.response,
                    sender="bot",
                    timestamp=response.timestamp,
                    metadata=response.metadata,
                )
                await websocket.send_text(bot_msg.model_dump_json())
                logger.info(f"[{session_id}] Bot ({response.intent}): {response.response[:80]}...")

            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)
                error_msg = WSMessage(
                    type="message",
                    content=(
                        "Xin lỗi anh/chị, hệ thống đang gặp sự cố. "
                        "Vui lòng thử lại sau ạ. 🙏"
                    ),
                    sender="bot",
                )
                await websocket.send_text(error_msg.model_dump_json())

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: session={session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)


# ============================================================
# REST API Endpoints
# ============================================================
@app.post("/api/chat", response_model=ChatResponse)
async def chat_http(request: ChatRequest):
    """HTTP endpoint for chat (fallback for non-WebSocket clients)."""
    response = await orchestrator.process_message(request.message, request.session_id)
    return response


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "VietBank AI Chatbot",
        "active_sessions": context_manager.get_active_sessions_count(),
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/exchange-rates")
async def get_exchange_rates():
    """Get current exchange rates from Vietcombank."""
    response = await exchange_rate_service.get_rates()
    return response.model_dump()


@app.get("/api/interest-rates")
async def get_interest_rates():
    """Get current interest rates."""
    response = interest_rate_service.get_all_rates()
    return response.model_dump()


@app.post("/api/reindex")
async def reindex_knowledge_base():
    """Force re-index the knowledge base documents."""
    try:
        rag_service.reindex()
        return {"status": "success", "message": "Knowledge base re-indexed successfully"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ============================================================
# Serve Frontend Static Files
# ============================================================
# Serve frontend index.html at root
@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the chat frontend."""
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return HTMLResponse(content=index_path.read_text(encoding="utf-8"))
    return HTMLResponse(
        content="<h1>Frontend not found</h1><p>Place frontend files in the frontend/ directory.</p>",
        status_code=404,
    )


# Mount static files (CSS, JS)
if FRONTEND_DIR.exists():
    app.mount("/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
    app.mount("/js", StaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")
