# 🏦 VietBank AI Chatbot

Trợ lý ảo tư vấn khách hàng cá nhân ngân hàng — chạy hoàn toàn local, 100% miễn phí.

## ✨ Tính năng

- 💬 **Chat real-time** qua WebSocket với giao diện premium
- 🧠 **Nhận diện ý định** tự động (8 loại intent)
- 📚 **RAG Pipeline** — truy vấn tài liệu nghiệp vụ ngân hàng
- 💱 **Tỷ giá real-time** từ Vietcombank API
- 💰 **Lãi suất** tiết kiệm & cho vay
- 🧵 **Nhớ ngữ cảnh** hội thoại, quản lý topic stack
- 🔒 **100% Local** — không gửi dữ liệu ra cloud

## 🛠️ Tech Stack

| Component | Technology |
|-----------|-----------|
| LLM | Qwen3 4B (Ollama) |
| Embedding | BGE-M3 (Ollama) |
| AI Framework | LangChain |
| Vector DB | ChromaDB |
| Backend | FastAPI + WebSocket |
| Frontend | HTML/CSS/JS |

## 📋 Yêu cầu hệ thống

- **Python** 3.10+
- **Ollama** ([ollama.com](https://ollama.com))
- **GPU**: NVIDIA (6GB+ VRAM khuyến nghị) hoặc CPU (chậm hơn)
- **RAM**: 12GB+

## 🚀 Cài đặt & Chạy

### Bước 1: Cài đặt Ollama

Tải và cài đặt Ollama từ [ollama.com](https://ollama.com).

### Bước 2: Tải models

```bash
ollama pull qwen3:4b
ollama pull bge-m3
```

### Bước 3: Cài đặt Python dependencies

```bash
cd backend
pip install -r requirements.txt
```

### Bước 4: Index tài liệu nghiệp vụ

```bash
cd backend
python -m scripts.index_documents
```

### Bước 5: Chạy server

```bash
cd backend
python run.py
```

### Bước 6: Mở trình duyệt

Truy cập [http://localhost:8000](http://localhost:8000) 🎉

## 📁 Cấu trúc dự án

```
banking-chatbot/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI + WebSocket
│   │   ├── config.py            # Configuration
│   │   ├── core/
│   │   │   ├── intent_classifier.py
│   │   │   ├── context_manager.py
│   │   │   ├── orchestrator.py
│   │   │   └── response_generator.py
│   │   ├── services/
│   │   │   ├── llm_service.py
│   │   │   ├── rag_service.py
│   │   │   ├── exchange_rate_service.py
│   │   │   └── interest_rate_service.py
│   │   ├── models/
│   │   │   ├── schemas.py
│   │   │   └── intents.py
│   │   └── utils/
│   │       └── prompt_templates.py
│   ├── knowledge_base/          # Tài liệu nghiệp vụ
│   ├── mock_data/               # Mock data
│   ├── scripts/
│   │   └── index_documents.py
│   ├── requirements.txt
│   └── run.py
├── frontend/
│   ├── index.html
│   ├── css/styles.css
│   └── js/app.js
└── README.md
```

## 🔌 API Endpoints

| Method | Endpoint | Mô tả |
|--------|----------|--------|
| WebSocket | `/ws/chat/{session_id}` | Real-time chat |
| POST | `/api/chat` | HTTP chat (fallback) |
| GET | `/api/health` | Health check |
| GET | `/api/exchange-rates` | Tỷ giá Vietcombank |
| GET | `/api/interest-rates` | Lãi suất |
| POST | `/api/reindex` | Re-index knowledge base |

## ⚙️ Cấu hình

Các biến môi trường (tùy chọn):

| Variable | Default | Mô tả |
|----------|---------|--------|
| `LLM_MODEL` | `qwen3:4b` | Model LLM |
| `EMBEDDING_MODEL` | `bge-m3` | Model embedding |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `PORT` | `8000` | Server port |

## 📝 License

MIT — Hoàn toàn miễn phí sử dụng.
