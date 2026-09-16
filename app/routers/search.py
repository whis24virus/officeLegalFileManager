"""
Hybrid Search API route — V3 Enhanced

This endpoint combines two search strategies:
1. SQLite FTS5 (Full-Text Search) — finds exact keyword matches
2. BGE-Large Semantic Search via ChromaDB — finds contextually similar documents
3. Cross-Encoder Re-Ranking — reorders semantic results for precision (V3)

Results are split into Exact Matches and Semantic Matches.
LLM answer generation is handled by the separate /api/rag endpoint (Two-Phase Response).
"""

import json
import logging
import re
import time

from fastapi import APIRouter, Depends, Query

from app.auth import get_current_department
from app.config import SEARCH_RESULTS_LIMIT, SNIPPET_LENGTH
from app.database import search_fts, get_document_by_id, get_department_vocabulary
import difflib
from app.services.embedder import embedder_service
from app.services.reranker import reranker_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["search"])

# Question-detection keywords
QUESTION_WORDS = {
    "who", "what", "where", "when", "why", "how",
    "can", "is", "does", "do", "tell", "show",
    "which", "whom", "whose", "will", "should",
}


def _parse_auto_tags(raw) -> list:
    """Parse auto_tags from JSON string to list."""
    if isinstance(raw, list):
        return raw
    try:
        return json.loads(raw) if raw else []
    except (json.JSONDecodeError, TypeError):
        return []


def _generate_snippet(text: str, query: str) -> str:
    """Generate a text snippet around the first occurrence of query words."""
    if not text:
        return ""

    text_lower = text.lower()
    query_words = query.lower().split()

    best_idx = -1
    for word in query_words:
        idx = text_lower.find(word)
        if idx != -1:
            best_idx = idx
            break

    if best_idx == -1:
        return text[:SNIPPET_LENGTH] + ("..." if len(text) > SNIPPET_LENGTH else "")

    half = SNIPPET_LENGTH // 2
    start = max(0, best_idx - half)
    end = min(len(text), best_idx + half)

    snippet = text[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."

    return snippet


@router.get("/search/exact")
def exact_search(
    q: str = Query(..., min_length=1, description="Search query text"),
    limit: int = Query(SEARCH_RESULTS_LIMIT, le=100, description="Max results"),
    department: str = Depends(get_current_department),
):
    """
    V5 Search: Returns EXACT file results instantly (SQLite).
    Semantic Search and LLM are decoupled for performance.
    """
    start_time = time.time()
    query_words = q.lower().split()
    primary_word = query_words[0] if query_words else q.lower()

    # Detect if query is a natural language question
    is_question = (
        q.strip().endswith("?")
        or (query_words and query_words[0] in QUESTION_WORDS)
    )

    # ── Step 1: FTS5 Exact/Prefix Keyword Search ──
    fts_results = search_fts(q, department, limit)
    logger.debug(f"FTS5 returned {len(fts_results)} results for '{q}' in dept '{department}'")

    exact_matches = []
    exact_doc_ids = set()
    for r in fts_results:
        doc_id = r["id"]
        doc = get_document_by_id(doc_id, department)
        if not doc:
            continue
        exact_doc_ids.add(doc_id)

        tags = _parse_auto_tags(doc.get("auto_tags", "[]"))

        # Calculate Matched Keywords using prefix matching
        tag_words = set()
        for tag in tags:
            tag_words.update(str(tag).lower().split())

        doc_text = doc.get("extracted_text", "")
        if doc_text:
            tag_words.update(doc_text.lower().split())

        clean_words = {re.sub(r'[^a-z0-9]', '', w) for w in tag_words}

        matched_keywords = []
        if primary_word:
            for w in clean_words:
                if w.startswith(primary_word) and len(w) > 2:
                    matched_keywords.append(w)

        if not matched_keywords:
            matched_keywords = [primary_word if primary_word else (tags[0] if tags else "Exact Match")]

        # Sort by length ascending so shorter cleaner words show first
        matched_keywords = sorted(list(set(matched_keywords)), key=len)

        exact_matches.append({
            "id": doc["id"],
            "title": doc["title"],
            "filename": doc["filename"],
            "filetype": doc["filetype"],
            "filesize": doc["filesize"],
            "department": doc["department"],
            "category": doc.get("category", "Other"),
            "auto_tags": tags,
            "snippet": _generate_snippet(doc.get("extracted_text", ""), q),
            "match_source": "exact",
            "matched_keywords": matched_keywords,
        })

    # ── Step 2: Did You Mean? & Autocomplete ──
    did_you_mean = None
    suggestions = []
    word_completions = []

    vocab = get_department_vocabulary(department)
    if vocab:
        if not exact_matches and primary_word:
            close_matches = difflib.get_close_matches(primary_word, vocab, n=3, cutoff=0.6)
            if close_matches:
                did_you_mean = close_matches[0]
                suggestions = close_matches

        if query_words:
            last_word = query_words[-1]
            if len(last_word) >= 2:
                completions = [v for v in vocab if v.startswith(last_word) and v != last_word]
                if completions:
                    completions.sort(key=len)
                    word_completions = completions[:5]

    search_time_ms = round((time.time() - start_time) * 1000, 2)

    return {
        "query": q,
        "department": department,
        "exact_matches": exact_matches,
        "did_you_mean": did_you_mean,
        "suggestions": suggestions,
        "word_completions": word_completions,
        "is_question": is_question,
        "search_time_ms": search_time_ms,
    }

@router.get("/search/semantic")
def semantic_search(
    q: str = Query(..., min_length=3, description="Search query text"),
    limit: int = Query(SEARCH_RESULTS_LIMIT, le=100, description="Max results"),
    department: str = Depends(get_current_department),
    exclude_ids: str = Query("", description="Comma-separated exact match IDs to exclude"),
):
    """
    V5 Semantic Search: Fetches vector results using BGE-Large and Cross-Encoder re-ranking.
    Should be called after a heavy debounce to preserve backend resources.
    """
    start_time = time.time()
    exact_doc_ids = set()
    if exclude_ids:
        for x in exclude_ids.split(","):
            if x.isdigit():
                exact_doc_ids.add(int(x))

    query_words = q.lower().split()
    primary_word = query_words[0] if query_words else q.lower()

    semantic_results = []
    semantic_matches = []
    try:
        query_embedding = embedder_service.generate_embedding(q)
        semantic_results = embedder_service.search_similar(query_embedding, department, limit)
        logger.debug(f"Semantic search returned {len(semantic_results)} results")
    except Exception as e:
        logger.warning(f"Semantic search failed: {e}")

    for result_tuple in semantic_results:
        doc_id, sim_score = result_tuple[0], result_tuple[1]
        chunk_text_content = result_tuple[2] if len(result_tuple) > 2 else ""

        if doc_id in exact_doc_ids:
            continue

        doc = get_document_by_id(doc_id, department)
        if not doc:
            continue

        tags = _parse_auto_tags(doc.get("auto_tags", "[]"))
        tag_words = []
        for tag in tags:
            tag_words.extend(str(tag).lower().split())

        matches = difflib.get_close_matches(primary_word, list(set(tag_words)), n=5, cutoff=0.3)
        matched_keywords = matches if matches else ([tags[0]] if tags else ["Semantic Match"])
        matched_keywords = sorted(list(set(matched_keywords)), key=len)

        semantic_matches.append({
            "id": doc["id"],
            "title": doc["title"],
            "filename": doc["filename"],
            "filetype": doc["filetype"],
            "filesize": doc["filesize"],
            "department": doc["department"],
            "category": doc.get("category", "Other"),
            "auto_tags": tags,
            "snippet": _generate_snippet(
                chunk_text_content or doc.get("extracted_text", ""), q
            ),
            "match_source": "semantic",
            "matched_keywords": matched_keywords,
            "relevance_score": round(sim_score, 4),
        })

    if semantic_matches:
        try:
            semantic_matches = reranker_service.rerank(q, semantic_matches)
        except Exception as e:
            logger.warning(f"Re-ranking failed, using original order: {e}")

    search_time_ms = round((time.time() - start_time) * 1000, 2)
    return {
        "semantic_matches": semantic_matches,
        "search_time_ms": search_time_ms,
    }
