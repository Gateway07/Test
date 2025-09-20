"""
Chunking and vectorizing pipeline.

- Chunking via langchain text splitters (TokenTextSplitter by default; optional recursive char splitter)
- Embedding via langchain_community.OllamaEmbeddings (default model: FRIDA)
- Vector store via langchain_chroma.Chroma with persistence
"""
from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

from langchain_community.embeddings import OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import TokenTextSplitter, RecursiveCharacterTextSplitter


@dataclass
class ChunkResult:
    """Result of chunking a single source text."""
    chunks: List[Document]


class Chunker:
    """Create text chunks from raw documents using token-based or character-based splitters."""

    def __init__(
        self,
        chunk_size: int = 512,
        overlap_size: int = 128,
        separators: Optional[List[str]] = None,
        use_token_splitter: bool = True,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.chunk_size = chunk_size
        self.overlap_size = overlap_size
        self.separators = separators or ["\n\n", "\n", ". ", " "]
        self.use_token_splitter = use_token_splitter
        self.logger = logger or logging.getLogger(__name__)

        # Initialize splitter
        if self.use_token_splitter:
            self.splitter = TokenTextSplitter(chunk_size=chunk_size, chunk_overlap=overlap_size)
        else:
            self.splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=overlap_size,
                separators=self.separators,
            )

    def chunk(self, texts: Sequence[Tuple[str, dict]]) -> List[Document]:
        """Chunk a sequence of (text, metadata) into LangChain Documents.

        Args:
            texts: Sequence of tuples (text, metadata_dict)

        Returns:
            List of Document chunks with merged metadata (including positional info where feasible).
        """
        all_docs: List[Document] = []
        for text, meta in texts:
            # Perform split
            parts = self.splitter.split_text(text)
            start = 0
            for idx, chunk in enumerate(parts):
                # best-effort positional estimation by finding chunk text from start onwards
                pos = text.find(chunk, start)
                if pos == -1:
                    pos = start
                start = pos + len(chunk)
                doc_meta = {
                    **meta,
                    "chunk_index": idx,
                    "char_start": pos,
                    "char_end": pos + len(chunk),
                    "total_chars": len(text),
                    "ingested_at": dt.datetime.utcnow().isoformat() + "Z",
                }
                all_docs.append(Document(page_content=chunk, metadata=doc_meta))
        self.logger.info(f"Chunked into {len(all_docs)} chunks (size={self.chunk_size}, overlap={self.overlap_size})")
        return all_docs


class Vectorizer:
    """Create embeddings and upsert into Chroma vector store."""

    def __init__(
        self,
        model: str = "FRIDA",
        collection: str = "rag-docs",
        persist_dir: str = ".\\chroma",
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.model = model
        self.collection = collection
        self.persist_dir = persist_dir
        self.logger = logger or logging.getLogger(__name__)

        self.embeddings = OllamaEmbeddings(model=model)
        self.vstore = Chroma(
            collection_name=self.collection,
            embedding_function=self.embeddings,
            persist_directory=self.persist_dir,
        )

    def rebuild_collection(self) -> None:
        """Delete the collection if exists and recreate it."""
        try:
            # Use underlying Chroma client to delete collection
            client = self.vstore._client  # type: ignore[attr-defined]
            if client and hasattr(client, "delete_collection"):
                try:
                    client.delete_collection(self.collection)
                    self.logger.info(f"Deleted existing collection: {self.collection}")
                except Exception:
                    pass
            # Recreate by reinitializing vstore
            self.vstore = Chroma(
                collection_name=self.collection,
                embedding_function=self.embeddings,
                persist_directory=self.persist_dir,
            )
        except Exception as exc:
            self.logger.warning(f"Failed to rebuild collection '{self.collection}': {exc}")

    def upsert(self, docs: List[Document]) -> None:
        """Upsert documents into Chroma store."""
        if not docs:
            return
        self.vstore.add_documents(docs)
        # Persist
        try:
            self.vstore.persist()
        except Exception:
            pass
        self.logger.info(f"Upserted {len(docs)} chunks into collection '{self.collection}' at {self.persist_dir}")

    def similarity_search(
        self, query: str, k: int = 8, include_scores: bool = False
    ) -> List[Tuple[Document, float]]:
        """Retrieve top-k similar chunks for a query.

        Returns a list of (Document, score) if include_scores else (Document, 0.0).
        """
        if include_scores:
            results = self.vstore.similarity_search_with_score(query, k=k)
            return results
        docs = self.vstore.similarity_search(query, k=k)
        return [(d, 0.0) for d in docs]
