"""
Local Generative AI Service — V3 Enhanced

Provides three capabilities:
1. RAG Answer Generation — Answer questions based on document context
2. Document Summarization — Pre-compute 2-3 sentence summaries on upload
3. Chunk Header Generation — Create contextual headers for document chunks

Uses google/flan-t5-base (~990MB, CPU-friendly, 100% local).
"""

import logging
import threading
import json
from transformers import T5Tokenizer, T5ForConditionalGeneration, TextIteratorStreamer
import torch
from threading import Thread
from app.config import LLM_MODEL_NAME

logger = logging.getLogger(__name__)


class LLMService:
    """
    Local LLM service using Flan-T5 for all generative AI tasks.
    Model is lazy-loaded on first use and cached in memory.
    Thread-safe for PyTorch MPS/CUDA.
    """

    def __init__(self):
        self._model = None
        self._tokenizer = None
        self._device = "mps" if torch.backends.mps.is_available() else "cpu"
        self._lock = threading.Lock()

    def _load_model(self):
        """Load the Flan-T5 model into memory."""
        if self._model is None:
            with self._lock:
                if self._model is None:
                    try:
                        logger.info(f"Loading Local LLM ({LLM_MODEL_NAME}) for RAG on {self._device}...")
                        self._tokenizer = T5Tokenizer.from_pretrained(LLM_MODEL_NAME)
                        self._model = T5ForConditionalGeneration.from_pretrained(LLM_MODEL_NAME)
                        self._model.to(self._device)
                        self._model.eval()
                    except Exception as e:
                        logger.error(f"Failed to load LLM: {e}")
                        self._model = "fallback"

    def _is_available(self) -> bool:
        """Check if the LLM is loaded and available."""
        self._load_model()
        return self._model is not None and self._model != "fallback"

    def generate_rag_answer(self, query: str, contexts: list) -> dict:
        """
        Generate a direct answer to a natural language question.

        Uses a summary-first strategy: if a pre-computed summary is available,
        it's used as primary context (much faster). Falls back to raw text.

        Args:
            query: The user's question.
            contexts: List of dicts with keys: 'text', 'filename', and optionally 'summary'.

        Returns:
            {"answer": str, "source": str}
        """
        if not self._is_available():
            return {"answer": "The local AI model is not available.", "source": None}

        if not contexts:
            return {
                "answer": "I couldn't find any relevant documents to answer your question.",
                "source": None,
            }

        best_doc = contexts[0]
        filename = best_doc.get("filename", "Unknown")

        # Prefer exact chunks retrieved by semantic search, but prepend summary for high-level context
        summary = best_doc.get("summary", "")
        raw_text = best_doc.get("text", "")[:1200]

        context_text = raw_text
        if summary and len(summary) > 20:
            context_text = f"Document Summary: {summary}\n\nSpecific Excerpt:\n{raw_text}"

        combined_context = context_text
        question = query

        prompt = f"""Read the following document context carefully. Answer the question specifically using the data provided.
If the question asks for a list or multiple items, you must provide all matching items.
Important: You must extract EVERY single item from the context that matches the query. Do not stop after the first item.

Context:
{context_text}

Question: {query}
Answer:"""

        try:
            with self._lock:
                input_ids = self._tokenizer(prompt, return_tensors="pt").input_ids.to(self._device)
                outputs = self._model.generate(
                    input_ids,
                    max_length=256,
                    num_beams=1,
                    early_stopping=True
                )
            answer = self._tokenizer.decode(outputs[0], skip_special_tokens=True).strip()
            return {"answer": answer, "source": filename}
        except Exception as e:
            logger.error(f"LLM RAG generation failed: {e}")
            return {"answer": "An error occurred while generating the answer.", "source": None}

    def generate_rag_stream(self, query: str, contexts: list):
        """
        Generate a direct answer via a generator, yielding chunks for SSE.
        """
        if not self._is_available():
            yield {"chunk": "The local AI model is not available.", "source": None}
            return

        if not contexts:
            yield {"chunk": "I couldn't find any relevant documents to answer your question.", "source": None}
            return

        best_doc = contexts[0]
        filename = best_doc.get("filename", "Unknown")

        # Prefer exact chunks retrieved by semantic search, but prepend summary for high-level context
        summary = best_doc.get("summary", "")
        raw_text = best_doc.get("text", "")[:1200]

        context_text = raw_text
        if summary and len(summary) > 20:
            context_text = f"Document Summary: {summary}\n\nSpecific Excerpt:\n{raw_text}"

        prompt = f"""Read the following document context carefully. Answer the question specifically using the data provided.
If the question asks for a list or multiple items, you must provide all matching items.
Important: You must extract EVERY single item from the context that matches the query. Do not stop after the first item.

Context:
{context_text}

Question: {query}
Answer:"""

        try:
            input_ids = self._tokenizer(prompt, return_tensors="pt").input_ids.to(self._device)
            streamer = TextIteratorStreamer(self._tokenizer, skip_special_tokens=True, skip_prompt=True)

            def generate_func():
                with self._lock:
                    self._model.generate(
                        input_ids,
                        streamer=streamer,
                        max_length=256,
                        num_beams=1,
                        early_stopping=True
                    )

            thread = Thread(target=generate_func)
            thread.start()

            yield {"source": filename}

            for new_text in streamer:
                if new_text:
                    yield {"chunk": new_text}
                    
        except Exception as e:
            logger.error(f"LLM RAG streaming failed: {e}")
            yield {"chunk": "An error occurred while generating the answer."}

    def generate_summary(self, text: str) -> str:
        """
        Generate a concise 2-3 sentence summary of a document.
        Used during file upload for faster RAG on cache misses.

        Args:
            text: The full extracted text of the document.

        Returns:
            A short summary string, or empty string on failure.
        """
        self._load_model()
        if not self._is_available() or not text or len(text.strip()) < 50:
            return ""

        try:
            truncated = text[:2000]
            prompt = f"Summarize the following document in 2-3 sentences:\n{truncated}"
            with self._lock:
                input_ids = self._tokenizer(prompt, return_tensors="pt").input_ids.to(self._device)
                outputs = self._model.generate(
                    input_ids,
                    max_length=100,
                    num_beams=2,
                    early_stopping=True
                )
            summary = self._tokenizer.decode(outputs[0], skip_special_tokens=True).strip()
            logger.debug(f"LLM: Generated summary ({len(summary)} chars)")
            return summary
        except Exception as e:
            logger.error(f"LLM summary generation failed: {e}")
            return ""

    def generate_chunk_header(self, doc_text: str) -> str:
        """
        V3: Generates a 1-sentence contextual header for chunks.
        """
        self._load_model()
        if self._model is None:
            return ""

        prompt = f"Summarize the main topic of this document in exactly one sentence:\n\n{doc_text[:2000]}\n\nOne sentence summary:"
        
        try:
            with self._lock:
                input_ids = self._tokenizer(prompt, return_tensors="pt").input_ids.to(self._device)
                outputs = self._model.generate(
                    input_ids,
                    max_length=40,
                    num_beams=2,
                    early_stopping=True,
                    no_repeat_ngram_size=2
                )
            return self._tokenizer.decode(outputs[0], skip_special_tokens=True)
        except Exception as e:
            logger.error(f"LLM Chunk Header failed: {e}")
            return ""

    def generate_question_variations(self, question: str, answer: str) -> list[str]:
        """
        V4: Generates 3 alternative ways to ask the same question, based on the answer.
        Used for proactive cache expansion.
        """
        self._load_model()
        if self._model is None:
            return []

        prompt = f"""
Given the following question and answer, generate exactly 3 alternative, distinctly phrased questions that a user might ask to get this exact same answer.
Return them as a numbered list (1., 2., 3.).

Original Question: {question}
Answer: {answer[:500]}

Alternative Questions:
"""
        try:
            with self._lock:
                input_ids = self._tokenizer(prompt, return_tensors="pt").input_ids.to(self._device)
                outputs = self._model.generate(
                    input_ids,
                    max_length=100,
                    num_beams=4,
                    early_stopping=True
                )
            text = self._tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            # Parse the numbered list
            variations = []
            for line in text.split('\n'):
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith('-') or line.startswith('*')):
                    # Clean up "1. ", "- ", etc.
                    clean = line.lstrip('0123456789.-* ').strip()
                    if clean:
                        variations.append(clean)
            
            return variations[:3]
        except Exception as e:
            logger.error(f"LLM Question Variations failed: {e}")
            return []


llm_service = LLMService()
