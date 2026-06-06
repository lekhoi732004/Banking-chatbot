"""
RAG Service — Retrieval-Augmented Generation pipeline using ChromaDB and BGE-M3.
Handles document indexing, semantic search, and context-aware response generation.
"""

import logging
from pathlib import Path
from typing import List, Optional

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import (
    CHROMA_COLLECTION_NAME,
    CHROMA_DB_DIR,
    KNOWLEDGE_BASE_DIR,
    RAG_CHUNK_OVERLAP,
    RAG_CHUNK_SIZE,
    RAG_TOP_K,
)
from app.services.llm_service import get_embeddings, get_llm
from app.utils.prompt_templates import RAG_RESPONSE_PROMPT

logger = logging.getLogger(__name__)


class RAGService:
    """Service for RAG pipeline: index documents, retrieve, and generate answers."""

    def __init__(self):
        self._vectorstore: Optional[Chroma] = None
        self._text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=RAG_CHUNK_SIZE,
            chunk_overlap=RAG_CHUNK_OVERLAP,
            separators=["\n## ", "\n### ", "\n#### ", "\n\n", "\n", "。", ".", " "],
        )

    def get_vectorstore(self) -> Chroma:
        """Get or create the ChromaDB vector store."""
        if self._vectorstore is None:
            embeddings = get_embeddings()
            persist_dir = str(CHROMA_DB_DIR)

            # Try to load existing DB
            try:
                self._vectorstore = Chroma(
                    collection_name=CHROMA_COLLECTION_NAME,
                    embedding_function=embeddings,
                    persist_directory=persist_dir,
                )
                # Check if it has documents
                count = self._vectorstore._collection.count()
                if count > 0:
                    logger.info(f"Loaded existing ChromaDB with {count} documents")
                else:
                    logger.warning("ChromaDB is empty, indexing knowledge base...")
                    self._index_knowledge_base()
            except Exception as e:
                logger.warning(f"Could not load ChromaDB: {e}. Creating new one...")
                self._vectorstore = Chroma(
                    collection_name=CHROMA_COLLECTION_NAME,
                    embedding_function=embeddings,
                    persist_directory=persist_dir,
                )
                self._index_knowledge_base()

        return self._vectorstore

    def _index_knowledge_base(self):
        """Index all documents in the knowledge base directory."""
        if not KNOWLEDGE_BASE_DIR.exists():
            logger.error(f"Knowledge base directory not found: {KNOWLEDGE_BASE_DIR}")
            return

        documents = self._load_documents()
        if not documents:
            logger.warning("No documents found in knowledge base")
            return

        # Split documents
        splits = self._text_splitter.split_documents(documents)
        logger.info(f"Split {len(documents)} documents into {len(splits)} chunks")

        # Add to vector store
        if self._vectorstore:
            self._vectorstore.add_documents(splits)
            logger.info(f"Indexed {len(splits)} chunks into ChromaDB")

    def _load_documents(self) -> List[Document]:
        """Load all .md files from the knowledge base directory."""
        documents = []
        md_files = list(KNOWLEDGE_BASE_DIR.glob("*.md"))
        logger.info(f"Found {len(md_files)} markdown files in knowledge base")

        for md_file in md_files:
            try:
                content = md_file.read_text(encoding="utf-8")
                doc = Document(
                    page_content=content,
                    metadata={
                        "source": md_file.name,
                        "topic": md_file.stem,
                    },
                )
                documents.append(doc)
                logger.info(f"Loaded: {md_file.name} ({len(content)} chars)")
            except Exception as e:
                logger.error(f"Failed to load {md_file.name}: {e}")

        return documents

    async def query(
        self,
        question: str,
        customer_type: str = "cá nhân",
        current_topic: str = "",
        chat_history: str = "",
    ) -> str:
        """Query the RAG pipeline and generate a response.

        Args:
            question: The user's question
            customer_type: 'cá nhân' or 'doanh nghiệp'
            current_topic: Current conversation topic
            chat_history: Formatted chat history string

        Returns:
            Generated response string
        """
        try:
            vectorstore = self.get_vectorstore()
            retriever = vectorstore.as_retriever(
                search_type="similarity",
                search_kwargs={"k": RAG_TOP_K},
            )

            # Retrieve relevant documents
            docs = retriever.invoke(question)

            if not docs:
                return (
                    "Xin lỗi anh/chị, em chưa tìm thấy thông tin phù hợp trong hệ thống. "
                    "Anh/chị vui lòng liên hệ hotline 1900-xxxx hoặc đến chi nhánh gần nhất "
                    "để được hỗ trợ chi tiết ạ."
                )

            # Format context from retrieved documents
            context = "\n\n---\n\n".join([
                f"[Nguồn: {doc.metadata.get('source', 'N/A')}]\n{doc.page_content}"
                for doc in docs
            ])

            # Build prompt
            prompt = ChatPromptTemplate.from_messages([
                ("system", RAG_RESPONSE_PROMPT),
                ("human", "{question}"),
            ])

            llm = get_llm()
            chain = prompt | llm

            # Generate response
            response = await chain.ainvoke({
                "customer_type": customer_type,
                "current_topic": current_topic or "chung",
                "context": context,
                "chat_history": chat_history or "Chưa có lịch sử",
                "question": question,
            })

            cleaned = self._clean_response(response.content)
            if cleaned:
                return cleaned

            logger.warning("RAG response generation returned empty text")
            return self._build_doc_fallback(question, docs)

        except Exception as e:
            logger.error(f"RAG query error: {e}", exc_info=True)
            return (
                "Xin lỗi anh/chị, hệ thống đang gặp sự cố khi tra cứu thông tin. "
                "Vui lòng thử lại sau hoặc liên hệ hotline 1900-xxxx ạ."
            )

    def reindex(self):
        """Force re-index all documents. Useful after updating knowledge base."""
        logger.info("Re-indexing knowledge base...")
        # Delete existing collection
        if self._vectorstore:
            try:
                self._vectorstore.delete_collection()
            except Exception:
                pass

        embeddings = get_embeddings()
        self._vectorstore = Chroma(
            collection_name=CHROMA_COLLECTION_NAME,
            embedding_function=embeddings,
            persist_directory=str(CHROMA_DB_DIR),
        )
        self._index_knowledge_base()
        logger.info("Re-indexing complete")

    @staticmethod
    def _clean_response(text: str) -> str:
        """Clean LLM response by removing thinking tags and artifacts."""
        import re
        # Remove <think>...</think> blocks that Qwen3 may produce
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        for marker in ("...done thinking.", "done thinking."):
            marker_index = text.lower().rfind(marker)
            if marker_index != -1:
                text = text[marker_index + len(marker):]
                break
        # Remove /no_think tags
        text = text.replace('/no_think', '').replace('/think', '')
        
        # Detect and strip common transition markers
        for marker in (
            "let me draft the response:",
            "here is the response:",
            "drafted response:",
            "response in vietnamese:",
            "here is the draft:"
        ):
            idx = text.lower().find(marker)
            if idx != -1:
                text = text[idx + len(marker):].strip()
                break

        # Remove excessive whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = text.strip()

        # Split into paragraphs and strip English reasoning paragraphs from the beginning
        paragraphs = text.split('\n\n')
        cleaned_paragraphs = []
        in_reasoning = True
        
        reasoning_indicators = (
            "tackle this query",
            "customer is asking",
            "first, i need to",
            "the rules say",
            "let me structure",
            "let me draft",
            "user's question",
            "original data",
            "so the response should",
            "i need to make sure",
        )
        english_stopwords = {"the", "and", "to", "of", "is", "in", "that", "it", "for", "on", "are", "as", "with", "at", "by", "an", "be", "this", "have", "from", "i", "need", "should", "query", "customer", "user", "response", "we", "can", "will"}

        for p in paragraphs:
            p_strip = p.strip()
            if not p_strip:
                continue
                
            if in_reasoning:
                p_lower = p_strip.lower()
                # Check indicator
                if any(indicator in p_lower for indicator in reasoning_indicators):
                    continue
                
                # Check word count
                words = [w.strip(".,?!:;()[]{}*\"'-") for w in p_lower.split()]
                words = [w for w in words if w]
                if words:
                    english_word_count = sum(1 for w in words if w in english_stopwords)
                    accented_word_count = sum(1 for w in words if any(c in w for c in "áàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵđĐ"))
                    if english_word_count >= 3 and accented_word_count <= 2:
                        continue
                in_reasoning = False
                
            cleaned_paragraphs.append(p)
            
        text = '\n\n'.join(cleaned_paragraphs)
        text = text.strip()

        reasoning_prefixes = (
            "thinking",
            "okay,",
            "ok,",
            "alright",
            "let me",
            "let's",
            "first,",
            "the user",
        )
        
        # Strip matching prefixes from the beginning of the text
        text_lower = text.lower()
        has_changed = True
        while has_changed:
            has_changed = False
            for prefix in reasoning_prefixes:
                if text_lower.startswith(prefix):
                    text = text[len(prefix):].strip()
                    text_lower = text.lower()
                    has_changed = True
                    break

        return text

    @staticmethod
    def _build_doc_fallback(question: str, docs: List[Document]) -> str:
        """Build a readable answer from retrieved chunks when the LLM output is unusable."""
        if not docs:
            return (
                "Dạ, em chưa tìm thấy thông tin phù hợp trong tài liệu nội bộ. "
                "Anh/chị vui lòng liên hệ hotline 1900-xxxx để được hỗ trợ chi tiết ạ."
            )

        question_lower = question.lower()
        account_docs = {
            doc.metadata.get("source")
            for doc in docs
        }
        if "giấy tờ" in question_lower and "mo_tai_khoan.md" in account_docs:
            section = RAGService._extract_markdown_section(
                KNOWLEDGE_BASE_DIR / "mo_tai_khoan.md",
                "## 3. Giấy tờ cần thiết",
            )
            if section:
                return (
                    "Dạ, để mở tài khoản, anh/chị chuẩn bị giấy tờ như sau:\n\n"
                    f"{section}\n\n"
                    "Thông tin có thể thay đổi theo chính sách ngân hàng. Anh/chị nên xác minh lại "
                    "qua hotline 1900-xxxx hoặc chi nhánh gần nhất trước khi giao dịch ạ."
                )

        # Account opening steps fallback
        is_asking_process_account = False
        if "mo_tai_khoan.md" in account_docs:
            q_clean = question_lower.strip("?.! ")
            if q_clean in ["mở tài khoản", "mo tai khoan"]:
                is_asking_process_account = True
            elif any(kw in question_lower for kw in ["quy trình", "các bước", "bước", "hướng dẫn", "cách mở", "đăng ký"]):
                non_process_kws = ["phí", "quyền lợi", "ưu đãi", "điều kiện", "giấy tờ", "yêu cầu", "lãi suất", "loại"]
                if not any(kw in question_lower for kw in non_process_kws):
                    is_asking_process_account = True

        if is_asking_process_account:
            section_quay = RAGService._extract_markdown_section(
                KNOWLEDGE_BASE_DIR / "mo_tai_khoan.md",
                "## 4. Quy trình mở tài khoản tại quầy giao dịch",
            )
            section_online = RAGService._extract_markdown_section(
                KNOWLEDGE_BASE_DIR / "mo_tai_khoan.md",
                "### 5.2. Quy trình mở tài khoản eKYC",
            )
            content = ""
            if section_quay:
                content += f"## Quy trình mở tài khoản tại quầy giao dịch\n\n{section_quay}\n\n"
            if section_online:
                content += f"## Quy trình mở tài khoản trực tuyến (eKYC)\n\n{section_online}\n\n"
            
            if content:
                return (
                    f"{content.strip()}\n\n"
                    "Thông tin có thể thay đổi theo chính sách ngân hàng. Anh/chị nên xác minh lại "
                    "qua hotline 1900-xxxx hoặc chi nhánh gần nhất trước khi giao dịch ạ."
                )

        # Credit card steps fallback
        is_asking_process_card = False
        if "the_tin_dung.md" in account_docs:
            q_clean = question_lower.strip("?.! ")
            if q_clean in ["thẻ tín dụng", "the tin dung", "mở thẻ tín dụng", "mo the tin dung"]:
                is_asking_process_card = True
            elif any(kw in question_lower for kw in ["quy trình", "các bước", "bước", "hướng dẫn", "cách mở", "đăng ký"]):
                non_process_kws = ["phí", "quyền lợi", "ưu đãi", "điều kiện", "giấy tờ", "yêu cầu", "lãi suất", "hạn mức", "loại"]
                if not any(kw in question_lower for kw in non_process_kws):
                    is_asking_process_card = True

        if is_asking_process_card:
            section_card = RAGService._extract_markdown_section(
                KNOWLEDGE_BASE_DIR / "the_tin_dung.md",
                "## 6. Quy trình đăng ký thẻ tín dụng",
            )
            if section_card:
                return (
                    f"{section_card.strip()}\n\n"
                    "Thông tin có thể thay đổi theo chính sách ngân hàng. Anh/chị nên xác minh lại "
                    "qua hotline 1900-xxxx hoặc chi nhánh gần nhất trước khi giao dịch ạ."
                )

        keywords = {
            word.strip(".,?!:;()[]{}\"'")
            for word in question_lower.split()
            if len(word.strip(".,?!:;()[]{}\"'")) >= 3
        }

        def score_doc(doc: Document) -> int:
            content = doc.page_content.lower()
            score = sum(1 for keyword in keywords if keyword in content)
            if "giấy tờ" in question_lower and "giấy tờ cần thiết" in content:
                score += 10
            if "mở tài khoản" in question_lower and "mở tài khoản" in content:
                score += 4
            return score

        best_doc = max(docs, key=score_doc)
        source = best_doc.metadata.get("source", "tài liệu nội bộ")
        lines = []
        for raw_line in best_doc.page_content.splitlines():
            line = raw_line.strip()
            if not line or line == "---":
                continue
            if line.startswith("#"):
                line = line.lstrip("#").strip()
            lines.append(line)
            if len(lines) >= 16:
                break

        excerpt = "\n".join(lines)
        if len(excerpt) > 1400:
            excerpt = excerpt[:1400].rsplit("\n", 1)[0]

        return (
            f"{excerpt}\n\n"
            "Thông tin có thể thay đổi theo chính sách ngân hàng. Anh/chị nên xác minh lại "
            "qua hotline 1900-xxxx hoặc chi nhánh gần nhất trước khi giao dịch ạ."
        )

    @staticmethod
    def _extract_markdown_section(path: Path, heading: str) -> str:
        if not path.exists():
            return ""

        content = path.read_text(encoding="utf-8")
        start = content.find(heading)
        if start == -1:
            return ""

        next_section = content.find("\n## ", start + len(heading))
        section = content[start: next_section if next_section != -1 else len(content)]
        lines = []
        for raw_line in section.splitlines():
            line = raw_line.strip()
            if not line or line == "---":
                continue
            lines.append(line)
            if len(lines) >= 24:
                break

        return "\n".join(lines)


# Global singleton
rag_service = RAGService()
