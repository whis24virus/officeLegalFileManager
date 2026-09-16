"""
RAG (Retrieval-Augmented Generation) API Endpoint — V3

This is a dedicated endpoint for asynchronous AI answer generation.
Called by the frontend AFTER search results have already been displayed
(Two-Phase Response pattern).

Flow:
1. Receive the user's question.
2. Check the Semantic QA Cache for a cached answer → instant return on HIT.
3. On MISS: embed the query → search ChromaDB → fetch summaries → run LLM.
4. Store the new Q+A pair in the cache.
5. Return the generated answer.
"""

import logging
import time
import json

from fastapi import APIRouter, Depends, Query, BackgroundTasks
from fastapi.responses import StreamingResponse

from app.auth import get_current_department
from app.database import get_document_by_id, get_document_summary
from app.services.embedder import embedder_service
from app.services.llm import llm_service
from app.services.qa_cache import qa_cache_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["rag"])


def generate_and_store_variations(question: str, answer: str, source: str, department: str):
    """Background task to generate question variations and cache them."""
    try:
        variations = llm_service.generate_question_variations(question, answer)
        if not variations:
            return
        
        embeddings = []
        valid_variations = []
        for v in variations:
            emb = embedder_service.generate_embedding(v)
            if emb is not None:
                embeddings.append(emb)
                valid_variations.append(v)
                
        if valid_variations:
            qa_cache_service.store_variations(valid_variations, embeddings, answer, source, department)
    except Exception as e:
        logger.error(f"Background cache expansion failed: {e}")


@router.get("/rag")
def generate_rag_answer(
    background_tasks: BackgroundTasks,
    q: str = Query(..., min_length=3, description="The user's question"),
    department: str = Depends(get_current_department),
):
    """
    Generate an AI answer to a natural language question.
    Uses Semantic QA Cache for instant repeat answers.
    """
    start_time = time.time()

    # Step 1: Embed the question
    query_embedding = embedder_service.generate_embedding(q)

    # Step 2: Check Semantic QA Cache
    cached = qa_cache_service.lookup(query_embedding, department)
    if cached:
        elapsed = round((time.time() - start_time) * 1000, 2)
        logger.info(f"RAG: Cache HIT for '{q[:50]}' in {elapsed}ms")
        def cache_stream_generator():
            yield f"data: {json.dumps({'source': cached['source']})}\n\n"
            yield f"data: {json.dumps({'chunk': cached['answer']})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        return StreamingResponse(cache_stream_generator(), media_type="text/event-stream")

    # Step 3: Cache MISS — Search for relevant documents
    semantic_results = embedder_service.search_similar(query_embedding, department, top_k=3)

    if not semantic_results:
        def not_found_stream_generator():
            yield f"data: {json.dumps({'chunk': 'I couldn\'t find any relevant documents to answer your question.'})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        return StreamingResponse(not_found_stream_generator(), media_type="text/event-stream")

    # Step 4: Build context from top results (prefer summaries)
    contexts = []
    for doc_id, sim_score, chunk_text in semantic_results:
        doc = get_document_by_id(doc_id, department)
        if not doc:
            continue

        summary = get_document_summary(doc_id)
        contexts.append({
            "text": chunk_text if chunk_text else doc.get("extracted_text", "")[:1500],
            "summary": summary,
            "filename": doc["filename"],
        })

    # Step 5: Stream answer via LLM
    def stream_generator():
        full_answer = ""
        source_file = None
        
        for chunk_data in llm_service.generate_rag_stream(q, contexts):
            yield f"data: {json.dumps(chunk_data)}\n\n"
            if "chunk" in chunk_data:
                full_answer += chunk_data["chunk"]
            if "source" in chunk_data:
                source_file = chunk_data["source"]
                
        # Send end marker
        yield f"data: {json.dumps({'done': True})}\n\n"
        
        # Step 6: Store in Semantic QA Cache after streaming finishes
        if full_answer and source_file:
            qa_cache_service.store(
                question=q,
                question_embedding=query_embedding,
                answer=full_answer.strip(),
                source_filename=source_file,
                department=department,
            )
            background_tasks.add_task(
                generate_and_store_variations,
                q,
                full_answer.strip(),
                source_file,
                department
            )

    return StreamingResponse(stream_generator(), media_type="text/event-stream")
