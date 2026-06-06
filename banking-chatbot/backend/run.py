"""
Quick start script for VietBank AI Chatbot.
Run: python run.py
"""

import uvicorn
from app.config import HOST, PORT

if __name__ == "__main__":
    print()
    print("=" * 60)
    print("  VietBank AI Chatbot")
    print("  Starting server...")
    print(f"  URL: http://localhost:{PORT}")
    print("=" * 60)
    print()

    uvicorn.run(
        "app.main:app",
        host=HOST,
        port=PORT,
        reload=True,
        log_level="info",
    )
