"""
Text Chunker — V3 Performance Layer

Splits extracted document text into overlapping chunks of configurable size.
Tries to split at sentence boundaries (periods, newlines) to avoid
cutting words or sentences in half.

Used by the upload pipeline to create chunk-level embeddings so the
vector search can find the exact paragraph containing the answer,
not just the right file.
"""

import re
import logging

logger = logging.getLogger(__name__)


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list:
    """
    Split text into overlapping chunks of approximately chunk_size characters.
    Tries to split at sentence boundaries to produce clean, readable chunks.

    Args:
        text: The full document text to split.
        chunk_size: Target size of each chunk in characters.
        overlap: Number of characters to overlap between consecutive chunks.

    Returns:
        A list of chunk strings. Returns [text] if text is shorter than chunk_size.
    """
    if not text or not text.strip():
        return []

    text = text.strip()

    # If text is short enough, return as single chunk
    if len(text) <= chunk_size:
        return [text]

    # Split text into sentences first
    # Matches periods, exclamation marks, question marks followed by whitespace
    sentences = re.split(r'(?<=[.!?\n])\s+', text)

    chunks = []
    current_chunk = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        # If adding this sentence would exceed chunk_size
        if len(current_chunk) + len(sentence) + 1 > chunk_size and current_chunk:
            chunks.append(current_chunk.strip())

            # Create overlap by keeping the tail of the current chunk
            if overlap > 0 and len(current_chunk) > overlap:
                # Find a good break point in the overlap region
                overlap_text = current_chunk[-overlap:]
                # Try to start at a sentence boundary within the overlap
                space_idx = overlap_text.find(' ')
                if space_idx != -1:
                    current_chunk = overlap_text[space_idx + 1:] + " " + sentence
                else:
                    current_chunk = overlap_text + " " + sentence
            else:
                current_chunk = sentence
        else:
            if current_chunk:
                current_chunk += " " + sentence
            else:
                current_chunk = sentence

    # Don't forget the last chunk
    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    # Filter out tiny chunks (less than 20 chars) that are just fragments
    chunks = [c for c in chunks if len(c) >= 20]

    logger.debug(f"Chunker: Split {len(text)} chars into {len(chunks)} chunks")
    return chunks
