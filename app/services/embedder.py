import logging
import json
import os
import numpy as np
from pathlib import Path
from typing import List, Tuple
from functools import lru_cache

from app.config import EMBEDDING_MODEL_NAME, VECTORS_DIR

logger = logging.getLogger(__name__)

class EmbeddingService:
    """
    Service for generating embeddings and performing vector search.
    The underlying sentence-transformers model is lazy-loaded on first use
    to improve application startup time and allow graceful fallbacks.
    """
    def __init__(self):
        self._model = None
        
    def _load_model(self):
        """Lazy load the sentence transformer model."""
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
        Generate a 384-dimensional embedding vector for the input text using MiniLM.
        Responses are cached in-memory so repeated searches bypass the AI model entirely!
        Returns a zero-vector if model fails to load.
        """
        self._load_model()
        if self._model == "fallback" or not text.strip():
            return np.zeros(384, dtype=np.float32)
            
        try:
            return self._model.encode(text)
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            return np.zeros(384, dtype=np.float32)

    def _get_vector_files(self, department: str) -> Tuple[Path, Path]:
        """Returns paths for the npy vectors file and the json id mapping file."""
        base_dir = Path(VECTORS_DIR) / department
        base_dir.mkdir(parents=True, exist_ok=True)
        npy_path = base_dir / "vectors.npy"
        json_path = base_dir / "doc_map.json"
        return npy_path, json_path

    def add_embedding(self, department: str, doc_id: int, embedding: np.ndarray):
        """
        Store the embedding vector for a given doc_id within a department.
        Uses a numpy array and a json file to maintain mappings.
        """
        npy_path, json_path = self._get_vector_files(department)
        
        doc_map = []
        if json_path.exists():
            with open(json_path, 'r') as f:
                doc_map = json.load(f)
                
        if npy_path.exists():
            vectors = np.load(npy_path)
            vectors = np.vstack([vectors, embedding])
        else:
            vectors = np.array([embedding])
            
        doc_map.append(doc_id)
        
        np.save(npy_path, vectors)
        with open(json_path, 'w') as f:
            json.dump(doc_map, f)

    def search_similar(self, query_embedding: np.ndarray, department: str, top_k: int) -> List[Tuple[int, float]]:
        """
        Find top_k similar documents to the query_embedding using cosine similarity.
        Returns a list of tuples (doc_id, similarity_score).
        """
        npy_path, json_path = self._get_vector_files(department)
        if not npy_path.exists() or not json_path.exists():
            return []
            
        with open(json_path, 'r') as f:
            doc_map = json.load(f)
            
        vectors = np.load(npy_path)
        if len(doc_map) == 0 or len(vectors) == 0:
            return []
            
        norm_q = np.linalg.norm(query_embedding)
        norm_v = np.linalg.norm(vectors, axis=1)
        
        if norm_q == 0:
            return []
            
        norm_v[norm_v == 0] = 1e-10
        similarities = np.dot(vectors, query_embedding) / (norm_v * norm_q)
        
        top_indices = np.argsort(similarities)[::-1][:top_k]
        
        results = []
        for idx in top_indices:
            score = float(similarities[idx])
            if score > 0.1:
                results.append((doc_map[idx], score))
                
        return results

embedder_service = EmbeddingService()
