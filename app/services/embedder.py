"""
Embedding Service — V3 Enhanced with Chunk-Level Embeddings

Manages all vector operations via ChromaDB:
- Document-level embeddings (backward compatible)
- Chunk-level embeddings with contextual headers (V3)
- Semantic similarity search returning chunk text for precise RAG

Uses BAAI/bge-large-en-v1.5 (1024-dimensional, normalized embeddings).
"""

import logging
import chromadb
import numpy as np
import threading
from typing import List, Tuple, Optional
from functools import lru_cache

from app.config import EMBEDDING_MODEL_NAME, VECTORS_DIR, EMBEDDING_DIMENSION

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Service for generating embeddings and performing vector search.
    V3: Supports both document-level and chunk-level embeddings in ChromaDB.
    """

    def __init__(self):
        self._model = None
        import os
        os.makedirs(VECTORS_DIR, exist_ok=True)
        try:
            self._chroma_client = chromadb.PersistentClient(path=VECTORS_DIR)
        except Exception as e:
            logger.error(f"Failed to init ChromaDB: {e}")
            self._chroma_client = None
        self._lock = threading.Lock()

    def _load_model(self):
        """Lazy load the sentence transformer model into memory."""
        if self._model is None:
            with self._lock:
                if self._model is None:
                    try:
                        from sentence_transformers import SentenceTransformer
                        logger.info(f"Loading embedding model: {EMBEDDING_MODEL_NAME}")
                        self._model = SentenceTransformer(EMBEDDING_MODEL_NAME)
                    except ImportError:
                        logger.warning("sentence-transformers not installed. Embeddings disabled.")
                        self._model = "fallback"
                    except Exception as e:
                        logger.error(f"Failed to load embedding model: {e}")
                        self._model = "fallback"

    @lru_cache(maxsize=1000)
    def generate_embedding(self, text: str) -> np.ndarray:
        """
        Generate an embedding vector for the input text.
        Cached in-memory so repeated searches bypass the model entirely.
        """
        self._load_model()
        if self._model == "fallback" or not text.strip():
            return np.zeros(EMBEDDING_DIMENSION, dtype=np.float32)

        try:
            with self._lock:
                embedding = self._model.encode(text, normalize_embeddings=True)
            return embedding
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            return np.zeros(EMBEDDING_DIMENSION, dtype=np.float32)

    def _clean_collection_name(self, department: str) -> str:
        """Generate a valid ChromaDB collection name."""
        clean_name = "".join(c if c.isalnum() else "_" for c in department.lower())
        if not clean_name:
            clean_name = "default_dept"
        if len(clean_name) < 3:
            clean_name = f"dept_{clean_name}"
        return clean_name

    def _get_collection(self, department: str):
        """Retrieves or creates a ChromaDB collection for the given department."""
        if not self._chroma_client:
            return None
        try:
            name = self._clean_collection_name(department)
            return self._chroma_client.get_or_create_collection(name=name)
        except Exception as e:
            logger.error(f"Error getting collection for {department}: {e}")
            return None

    # ── Document-Level Embedding (Backward Compatible) ──

    def add_embedding(self, department: str, doc_id: int, embedding: np.ndarray):
        """Store a single document-level embedding. Backward compatible with V2."""
        collection = self._get_collection(department)
        if not collection:
            return

        try:
            collection.upsert(
                embeddings=[embedding.tolist()],
                ids=[str(doc_id)]
            )
        except Exception as e:
            logger.error(f"Failed to add embedding for doc_id {doc_id}: {e}")

    # ── Chunk-Level Embeddings (V3) ──

    def add_chunks(
        self,
        department: str,
        doc_id: int,
        chunks: List[dict],
    ) -> None:
        """
        Store multiple chunk embeddings for a single document.

        Each chunk dict must contain:
            - "embedding": np.ndarray
            - "text": str (the chunk text)
            - "header": str (the contextual header)

        Chunk IDs are formatted as: "{doc_id}_chunk_{i}"
        Metadata stores: doc_id, chunk_index, text snippet (for RAG context)
        """
        collection = self._get_collection(department)
        if not collection:
            return

        try:
            # First, remove any existing chunks for this doc_id
            self._remove_doc_chunks(collection, doc_id)

            ids = []
            embeddings = []
            metadatas = []
            documents = []

            for i, chunk in enumerate(chunks):
                chunk_id = f"{doc_id}_chunk_{i}"
                ids.append(chunk_id)
                embeddings.append(chunk["embedding"].tolist())
                # Store the chunk text in metadata for retrieval during RAG
                # ChromaDB metadata values must be str, int, float, or bool
                metadatas.append({
                    "doc_id": doc_id,
                    "chunk_index": i,
                    "header": chunk.get("header", "")[:200],
                })
                # Store full chunk text as 'document' (ChromaDB's text field)
                documents.append(chunk["text"][:1000])

            if ids:
                collection.upsert(
                    ids=ids,
                    embeddings=embeddings,
                    metadatas=metadatas,
                    documents=documents,
                )
                logger.info(
                    f"Stored {len(ids)} chunks for doc_id={doc_id} in dept={department}"
                )

        except Exception as e:
            logger.error(f"Failed to add chunks for doc_id {doc_id}: {e}")

    def _remove_doc_chunks(self, collection, doc_id: int) -> None:
        """Remove all existing chunk entries for a document."""
        try:
            # Query for all IDs matching this doc_id
            existing = collection.get(
                where={"doc_id": doc_id},
                include=[]
            )
            if existing and existing.get("ids"):
                collection.delete(ids=existing["ids"])
        except Exception:
            # If where filter fails (e.g., no metadata), try by ID prefix
            try:
                # Fallback: delete the old single-document embedding
                collection.delete(ids=[str(doc_id)])
            except Exception:
                pass

    # ── Search ──

    def search_similar(
        self,
        query_embedding: np.ndarray,
        department: str,
        top_k: int,
    ) -> List[Tuple[int, float, str]]:
        """
        Query ChromaDB for the most similar documents/chunks.

        Returns:
            List of tuples: (doc_id, similarity_score, chunk_text)
            chunk_text is the matched chunk content (or empty for doc-level matches).
        """
        collection = self._get_collection(department)
        if not collection:
            return []

        try:
            if collection.count() == 0:
                return []

            results = collection.query(
                query_embeddings=[query_embedding.tolist()],
                n_results=min(top_k, collection.count()),
                include=["distances", "metadatas", "documents"],
            )

            matches = []
            seen_doc_ids = set()

            if results and results.get("ids") and results["ids"][0]:
                for i, id_str in enumerate(results["ids"][0]):
                    distance = results["distances"][0][i]
                    sim = max(0.0, 1.0 - (distance / 2.0))

                    if sim <= 0.1:
                        continue

                    metadata = results["metadatas"][0][i] if results.get("metadatas") else None
                    if not metadata:
                        metadata = {}

                    document = results["documents"][0][i] if results.get("documents") else ""

                    # Extract doc_id from metadata or from the ID string
                    if "doc_id" in metadata:
                        doc_id = int(metadata["doc_id"])
                    else:
                        # Backward compatible: ID is just the doc_id string
                        try:
                            doc_id = int(id_str.split("_")[0])
                        except (ValueError, IndexError):
                            doc_id = int(id_str)

                    # Deduplicate: only keep the best chunk per document
                    if doc_id in seen_doc_ids:
                        continue
                    seen_doc_ids.add(doc_id)

                    chunk_text = document or ""
                    matches.append((doc_id, float(sim), chunk_text))

            matches.sort(key=lambda x: x[1], reverse=True)
            return matches

        except Exception as e:
            logger.error(f"Failed to query ChromaDB: {e}")
            return []


embedder_service = EmbeddingService()
