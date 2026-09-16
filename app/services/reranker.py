"""
Cross-Encoder Re-Ranker — V3 Performance Layer

After the initial bi-encoder (BGE-Large) returns approximate results from
ChromaDB, the re-ranker reads each query + candidate pair together using
a Cross-Encoder model for much more accurate relevance scoring.

This is the same technique used by Microsoft Bing internally.
The model is small (~80MB) and adds ~300-500ms to the search pipeline.

Since we use Two-Phase Async Response (Phase 4), this re-ranking happens
in the background while the user already sees initial results.
"""

import logging
import threading
from typing import List

logger = logging.getLogger(__name__)


class ReRankerService:
    """
    Cross-encoder re-ranking service.
    Uses `cross-encoder/ms-marco-MiniLM-L-6-v2` for fast, accurate re-ranking.
    """

    def __init__(self):
        self._model = None
        self._lock = threading.Lock()

    def _load_model(self):
        """Lazy-load the cross-encoder model."""
        if self._model is None:
            with self._lock:
                if self._model is None:
                    try:
                        from sentence_transformers import CrossEncoder
                        model_name = "cross-encoder/ms-marco-MiniLM-L-6-v2"
                        logger.info(f"Loading Cross-Encoder re-ranker: {model_name}")
                        self._model = CrossEncoder(model_name)
                    except ImportError:
                        logger.warning("sentence-transformers not installed. Re-ranking disabled.")
                        self._model = "fallback"
                    except Exception as e:
                        logger.error(f"Failed to load re-ranker model: {e}")
                        self._model = "fallback"

    def rerank(self, query: str, candidates: List[dict]) -> List[dict]:
        """
        Re-rank a list of candidate result dicts by cross-encoder relevance.

        Each candidate dict should have a 'snippet' or 'title' field.
        Returns the same list sorted by cross-encoder score (most relevant first).

        Args:
            query: The user's search query string.
            candidates: List of result dicts from the search pipeline.

        Returns:
            The same list re-ordered by cross-encoder relevance score.
        """
        self._load_model()
        if self._model == "fallback" or not candidates:
            return candidates

        try:
            # Build query-candidate pairs for the cross-encoder
            pairs = []
            for candidate in candidates:
                # Use snippet as the primary text, fall back to title
                text = candidate.get("snippet", "") or candidate.get("title", "")
                pairs.append([query, text])

            # Score all pairs in a single batch (much faster than one-by-one)
            with self._lock:
                scores = self._model.predict(pairs)

            # Attach scores and sort by descending relevance
            scored_candidates = list(zip(candidates, scores))
            scored_candidates.sort(key=lambda x: x[1], reverse=True)

            reranked = [candidate for candidate, score in scored_candidates]

            logger.debug(
                f"ReRanker: Re-ranked {len(candidates)} candidates. "
                f"Top score: {max(scores):.4f}, Bottom: {min(scores):.4f}"
            )
            return reranked

        except Exception as e:
            logger.error(f"Re-ranking failed, returning original order: {e}")
            return candidates


reranker_service = ReRankerService()
