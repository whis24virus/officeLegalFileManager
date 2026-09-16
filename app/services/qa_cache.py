"""
Semantic QA Cache — V3 Performance Layer

Stores question→answer pairs in a ChromaDB collection per department.
On a new question, converts it to a vector and checks if a semantically
similar question was already answered. If the cosine similarity exceeds
the threshold, returns the cached answer instantly (10ms vs 5-10s for LLM).

Cache is automatically invalidated when files are uploaded or deleted
in a department, ensuring answers are never stale.
"""

import logging
import chromadb
import numpy as np
from typing import Optional

from app.config import VECTORS_DIR

logger = logging.getLogger(__name__)


class QACacheService:
    """
    Semantic cache for RAG question-answer pairs.
    Uses a separate ChromaDB collection per department to prevent cross-contamination.
    """

    # Cosine similarity threshold for a cache hit.
    # 0.92 = very strict (only near-identical questions match)
    # 0.85 = moderate (similar rephrases match)
    SIMILARITY_THRESHOLD = 0.90

    def __init__(self):
        import os
        os.makedirs(VECTORS_DIR, exist_ok=True)
        try:
            self._chroma_client = chromadb.PersistentClient(path=VECTORS_DIR)
        except Exception as e:
            logger.error(f"QACache: Failed to init ChromaDB client: {e}")
            self._chroma_client = None

    def _get_collection_name(self, department: str) -> str:
        """Generate a valid ChromaDB collection name for the QA cache."""
        clean = "".join(c if c.isalnum() else "_" for c in department.lower())
        if len(clean) < 3:
            clean = f"dept_{clean}"
        return f"qa_cache_{clean}"

    def _get_collection(self, department: str):
        """Get or create the QA cache collection for a department."""
        if not self._chroma_client:
            return None
        try:
            name = self._get_collection_name(department)
            return self._chroma_client.get_or_create_collection(name=name)
        except Exception as e:
            logger.error(f"QACache: Error getting collection for {department}: {e}")
            return None

    def lookup(self, question_embedding: np.ndarray, department: str) -> Optional[dict]:
        """
        Check if a semantically similar question was already answered.

        Args:
            question_embedding: The vector representation of the new question.
            department: The department scope.

        Returns:
            {"answer": str, "source": str, "cache_hit": True} on HIT, or None on MISS.
        """
        collection = self._get_collection(department)
        if not collection or collection.count() == 0:
            return None

        try:
            results = collection.query(
                query_embeddings=[question_embedding.tolist()],
                n_results=1
            )

            if not results or not results.get("ids") or not results["ids"][0]:
                return None

            distance = results["distances"][0][0]
            # Convert L2 Squared distance to cosine similarity (normalized embeddings)
            similarity = max(0.0, 1.0 - (distance / 2.0))

            if similarity >= self.SIMILARITY_THRESHOLD:
                metadata = results["metadatas"][0][0]
                logger.info(
                    f"QACache HIT: similarity={similarity:.4f} >= {self.SIMILARITY_THRESHOLD} "
                    f"for dept={department}"
                )
                return {
                    "answer": metadata.get("answer", ""),
                    "source": metadata.get("source", "Unknown"),
                    "cache_hit": True,
                }

            logger.debug(
                f"QACache MISS: similarity={similarity:.4f} < {self.SIMILARITY_THRESHOLD} "
                f"for dept={department}"
            )
            return None

        except Exception as e:
            logger.error(f"QACache lookup failed: {e}")
            return None

    def store(
        self,
        question: str,
        question_embedding: np.ndarray,
        answer: str,
        source_filename: str,
        department: str,
    ) -> None:
        """
        Store a new question→answer pair in the semantic cache.

        Args:
            question: The original question text (stored as document for debugging).
            question_embedding: The vector of the question.
            answer: The LLM-generated answer.
            source_filename: The file the answer was derived from.
            department: The department scope.
        """
        collection = self._get_collection(department)
        if not collection:
            return

        try:
            import hashlib
            # Use a hash of the question as a unique ID to prevent exact duplicates
            q_hash = hashlib.md5(question.lower().strip().encode()).hexdigest()[:16]
            doc_id = f"qa_{q_hash}"

            collection.upsert(
                ids=[doc_id],
                embeddings=[question_embedding.tolist()],
                documents=[question],
                metadatas=[{
                    "answer": answer,
                    "source": source_filename,
                }]
            )
            logger.info(f"QACache: Stored answer for '{question[:50]}...' in dept={department}")

        except Exception as e:
            logger.error(f"QACache store failed: {e}")

    def store_variations(
        self,
        questions: list[str],
        question_embeddings: list[np.ndarray],
        answer: str,
        source_filename: str,
        department: str,
    ) -> None:
        """
        V4: Store multiple variations of a question mapped to the same answer.
        """
        collection = self._get_collection(department)
        if not collection or not questions:
            return

        try:
            import hashlib
            ids = []
            documents = []
            embeddings = []
            metadatas = []
            
            for q, emb in zip(questions, question_embeddings):
                q_hash = hashlib.md5(q.lower().strip().encode()).hexdigest()[:16]
                ids.append(f"qa_{q_hash}")
                documents.append(q)
                embeddings.append(emb.tolist())
                metadatas.append({
                    "answer": answer,
                    "source": source_filename,
                })

            collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas
            )
            logger.info(f"QACache: Stored {len(questions)} variations in dept={department}")

        except Exception as e:
            logger.error(f"QACache store_variations failed: {e}")

    def invalidate(self, department: str) -> None:
        """
        Wipe the entire QA cache for a department.
        Called when files are uploaded or deleted to prevent stale answers.
        """
        if not self._chroma_client:
            return

        try:
            name = self._get_collection_name(department)
            self._chroma_client.delete_collection(name=name)
            logger.info(f"QACache: Invalidated cache for dept={department}")
        except Exception as e:
            # Collection might not exist yet — that's fine
            logger.debug(f"QACache: Nothing to invalidate for {department}: {e}")


qa_cache_service = QACacheService()
