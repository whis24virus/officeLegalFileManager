"""
Hybrid Search API route for Office Legal File Manager.

This endpoint combines two search strategies:
1. SQLite FTS5 (Full-Text Search) — finds exact keyword matches
2. MiniLM Semantic Search — finds contextually similar documents

Results are merged, deduplicated, scored, and ranked.
All queries are HARD-SCOPED to the user's department.

The search flow:
    Query: "lease agreement for office"
        → FTS5 finds docs containing words "lease", "agreement", "office"
        → MiniLM finds docs semantically about rentals/leases/properties
        → Merge & rank → Return top results with text snippets
"""

import json
import logging
import time

from fastapi import APIRouter, Depends, Query

from app.auth import get_current_department
from app.config import SEARCH_RESULTS_LIMIT, FTS_WEIGHT, SEMANTIC_WEIGHT, SNIPPET_LENGTH
from app.database import search_fts, get_document_by_id, get_department_vocabulary
import difflib
from app.services.embedder import embedder_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["search"])


def _parse_auto_tags(raw) -> list:
    """Parse auto_tags from JSON string to list."""
    if isinstance(raw, list):
        return raw
    try:
        return json.loads(raw) if raw else []
    except (json.JSONDecodeError, TypeError):
        return []


def _generate_snippet(text: str, query: str) -> str:
    """
    Generate a text snippet around the first occurrence of query words.
    If query words are found, centers the snippet around them.
    Otherwise, returns the beginning of the text.
    """
    if not text:
        return ""

    text_lower = text.lower()
    query_words = query.lower().split()

    # Try to find the first query word in the text
    best_idx = -1
    for word in query_words:
        idx = text_lower.find(word)
        if idx != -1:
            best_idx = idx
            break

    if best_idx == -1:
        # No match found, return beginning of text
        return text[:SNIPPET_LENGTH] + ("..." if len(text) > SNIPPET_LENGTH else "")

    # Center snippet around the match
    half = SNIPPET_LENGTH // 2
    start = max(0, best_idx - half)
    end = min(len(text), best_idx + half)

    snippet = text[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."

    return snippet


@router.get("/search")
def hybrid_search(
    q: str = Query(..., min_length=1, description="Search query text"),
    limit: int = Query(SEARCH_RESULTS_LIMIT, le=100, description="Max results"),
    department: str = Depends(get_current_department),
):
    """
    Perform a split search returning Exact Matches and Semantic Matches separately.
    Also provides 'Did you mean?' functionality using department vocabulary.
    """
    start_time = time.time()
    query_words = q.lower().split()
    primary_word = query_words[0] if query_words else q.lower()

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
        
        # Calculate Matched Keywords using prefix matching for Exact matches
        tag_words = set()
        for tag in tags:
            tag_words.update(str(tag).lower().split())
            
        doc_text = doc.get("extracted_text", "")
        if doc_text:
            tag_words.update(doc_text.lower().split())
        
        import re
        clean_words = {re.sub(r'[^a-z0-9]', '', w) for w in tag_words}
        
        # Find all words that start with the primary query word
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
            "matched_keywords": matched_keywords
        })

    # ── Step 2: MiniLM Semantic Search ──
    semantic_results = []
    semantic_matches = []
    try:
        query_embedding = embedder_service.generate_embedding(q)
        semantic_results = embedder_service.search_similar(query_embedding, department, limit)
        logger.debug(f"Semantic search returned {len(semantic_results)} results")
    except Exception as e:
        logger.warning(f"Semantic search failed: {e}")

    for doc_id, sim_score in semantic_results:
        if doc_id in exact_doc_ids:
            continue  # Don't show duplicates in semantic section
            
        doc = get_document_by_id(doc_id, department)
        if not doc:
            continue
            
        tags = _parse_auto_tags(doc.get("auto_tags", "[]"))
        
        # Calculate Matched Keyword using difflib against tags
        # Extract individual words from tags
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
            "snippet": _generate_snippet(doc.get("extracted_text", ""), q),
            "match_source": "semantic",
            "matched_keywords": matched_keywords,
            "relevance_score": round(sim_score, 4)
        })

    # ── Step 3: Did You Mean? & Autocomplete (Department-Aware) ──
    did_you_mean = None
    suggestions = []
    word_completions = []
    
    vocab = get_department_vocabulary(department)
    if vocab:
        if not exact_matches and primary_word:
            # Find closest words to the primary query word for spell correction
            close_matches = difflib.get_close_matches(primary_word, vocab, n=3, cutoff=0.6)
            if close_matches:
                did_you_mean = close_matches[0]
                suggestions = close_matches
                
        # Autocomplete Logic: Find words in vocab that start with the last word the user is typing
        if query_words:
            last_word = query_words[-1]
            if len(last_word) >= 2:  # Only suggest after 2 characters
                completions = [v for v in vocab if v.startswith(last_word) and v != last_word]
                if completions:
                    # Sort by length and take top 5
                    completions.sort(key=len)
                    word_completions = completions[:5]

    search_time_ms = round((time.time() - start_time) * 1000, 2)

    return {
        "query": q,
        "department": department,
        "exact_matches": exact_matches,
        "semantic_matches": semantic_matches,
        "did_you_mean": did_you_mean,
        "suggestions": suggestions,
        "word_completions": word_completions,
        "search_time_ms": search_time_ms,
    }
