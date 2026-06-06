"""
Script to index knowledge base documents into ChromaDB.
Run this after adding/updating documents in the knowledge_base/ directory.

Usage:
    cd backend
    python -m scripts.index_documents
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    """Index all knowledge base documents into ChromaDB."""
    from app.config import KNOWLEDGE_BASE_DIR, CHROMA_DB_DIR
    from app.services.rag_service import rag_service

    print()
    print("=" * 60)
    print("  Knowledge Base Indexer")
    print("=" * 60)
    print()

    # Check knowledge base directory
    if not KNOWLEDGE_BASE_DIR.exists():
        print(f"Error: Knowledge base directory not found: {KNOWLEDGE_BASE_DIR}")
        sys.exit(1)

    md_files = list(KNOWLEDGE_BASE_DIR.glob("*.md"))
    print(f"Knowledge base: {KNOWLEDGE_BASE_DIR}")
    print(f"Found {len(md_files)} documents:")
    for f in md_files:
        size_kb = f.stat().st_size / 1024
        print(f"   - {f.name} ({size_kb:.1f} KB)")
    print()

    # Force reindex
    print("Indexing documents into ChromaDB...")
    print(f"ChromaDB directory: {CHROMA_DB_DIR}")
    print()

    rag_service.reindex()

    # Verify
    vectorstore = rag_service.get_vectorstore()
    count = vectorstore._collection.count()
    print()
    print(f"Indexing complete! {count} chunks stored in ChromaDB.")
    print()

    # Test query
    print("Testing retrieval with sample query...")
    test_query = "Điều kiện mở tài khoản thanh toán?"
    docs = vectorstore.similarity_search(test_query, k=3)
    print(f"   Query: \"{test_query}\"")
    print(f"   Found {len(docs)} relevant chunks:")
    for i, doc in enumerate(docs, 1):
        preview = doc.page_content[:100].replace("\n", " ")
        print(f"   {i}. [{doc.metadata.get('source', '?')}] {preview}...")
    print()
    print("Done! You can now start the chatbot server.")


if __name__ == "__main__":
    main()
