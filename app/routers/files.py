"""
File management API routes for Office Legal File Manager.

All endpoints are department-scoped via the get_current_department dependency.
This means every request reads the department from the session cookie and
ONLY accesses files belonging to that department.

Endpoints:
    POST /upload   - Upload a file with metadata, run full processing pipeline
    GET  /         - List all files in current department
    GET  /{id}     - Get detailed file info (includes text preview)
    GET  /{id}/download - Download the original file
    DELETE /{id}   - Delete a file and clean up all indexes
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse as FastAPIFileResponse

from app.auth import get_current_department
from app.config import ALLOWED_EXTENSIONS, MAX_FILE_SIZE_BYTES, SNIPPET_LENGTH
from app.database import (
    insert_document,
    update_document_tags_and_embedding,
    update_document_text_tags_embedding,
    get_documents_by_department,
    get_document_by_id,
    delete_document,
)
from app.services.storage import save_file, delete_file, get_file_path
from app.services.extractor import extract_text
from app.services.tagger import generate_tags
from app.services.embedder import embedder_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["files"])


def _parse_auto_tags(raw: str) -> list:
    """Parse auto_tags from JSON string stored in DB to a Python list."""
    if isinstance(raw, list):
        return raw
    try:
        return json.loads(raw) if raw else []
    except (json.JSONDecodeError, TypeError):
        return []


def _doc_to_response(doc: dict) -> dict:
    """
    Convert a raw database row dict into the shape the frontend expects.
    The frontend (app.js) reads: id, title, filename, filetype, filesize,
    department, category, notes, auto_tags, created_at, uploaded_by.
    """
    return {
        "id": doc["id"],
        "title": doc["title"],
        "filename": doc["filename"],
        "filetype": doc["filetype"],
        "filesize": doc["filesize"],
        "department": doc["department"],
        "category": doc.get("category", "Other"),
        "notes": doc.get("notes", ""),
        "auto_tags": _parse_auto_tags(doc.get("auto_tags", "[]")),
        "created_at": doc.get("created_at", ""),
        "uploaded_by": doc.get("uploaded_by", "system"),
    }


def process_file_background(doc_id: int, filepath: str, ext: str, original_filename: str, department: str):
    """Heavy lifting background task: OCR, TF-IDF, and MiniLM."""
    try:
        # Step 2: Extract text
        abs_path = get_file_path(filepath)
        extracted_text = extract_text(abs_path, ext)
        logger.info(f"Background: Extracted {len(extracted_text)} chars of text from {original_filename}")

        # Step 3: Generate auto-tags
        auto_tags = generate_tags(extracted_text)
        logger.info(f"Background: Generated {len(auto_tags)} auto-tags: {auto_tags}")

        # Step 4: Generate embedding
        try:
            embedding = embedder_service.generate_embedding(extracted_text)
            emb_id = embedder_service.add_embedding(department, doc_id, embedding)
        except Exception as e:
            logger.warning(f"Background: Embedding generation failed: {e}")
            emb_id = -1

        # Step 5: Update database
        update_document_text_tags_embedding(doc_id, extracted_text, auto_tags, emb_id if emb_id else doc_id)
        logger.info(f"Background: Completed processing for {original_filename}")
    except Exception as e:
        logger.error(f"Background processing failed for {original_filename}: {e}")
        update_document_text_tags_embedding(doc_id, "", ["❌ Error"], -1)


@router.post("/upload")
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(...),
    category: str = Form("Other"),
    notes: str = Form(""),
    department: str = Depends(get_current_department),
):
    """
    Upload a file instantly using background processing:
    1. Validate file type and size
    2. Save file to disk under storage/{department}/
    3. Insert a skeleton metadata record into SQLite
    4. Enqueue background task for OCR/Embeddings
    5. Return immediately
    """
    # ── Validate file extension ──
    original_filename = file.filename or "unknown"
    ext = os.path.splitext(original_filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' not allowed. Allowed: {ALLOWED_EXTENSIONS}",
        )

    # ── Read file data ──
    file_data = await file.read()
    if len(file_data) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE_BYTES // (1024*1024)} MB",
        )

    # ── Step 1: Save to disk ──
    filepath, filesize = save_file(file_data, department, original_filename)
    logger.info(f"File saved: {filepath} ({filesize} bytes)")

    # ── Step 2: Insert skeleton into database ──
    doc_id = insert_document(
        title=title,
        filename=original_filename,
        filepath=filepath,
        filetype=ext.lstrip("."),
        filesize=filesize,
        department=department,
        category=category,
        notes=notes,
        auto_tags=["⏳ Processing"],
        extracted_text="",
    )
    logger.info(f"Document inserted with ID: {doc_id}")

    # ── Step 3: Add background task ──
    background_tasks.add_task(
        process_file_background,
        doc_id=doc_id,
        filepath=filepath,
        ext=ext,
        original_filename=original_filename,
        department=department
    )

    # ── Return the saved document immediately ──
    doc = get_document_by_id(doc_id, department)
    if doc:
        return _doc_to_response(doc)
    return {
        "id": doc_id,
        "title": title,
        "filename": original_filename,
        "filetype": ext.lstrip("."),
        "filesize": filesize,
        "department": department,
        "category": category,
        "notes": notes,
        "auto_tags": ["⏳ Processing"],
        "created_at": "",
        "uploaded_by": "system",
    }


@router.get("/")
def list_files(department: str = Depends(get_current_department)):
    """
    List all files belonging to the current user's department.
    Results are ordered by most recently uploaded first.
    The department filter is applied directly in the SQL query.
    """
    docs = get_documents_by_department(department)
    return [_doc_to_response(doc) for doc in docs]


@router.get("/{file_id}")
def get_file_detail(file_id: int, department: str = Depends(get_current_department)):
    """
    Get detailed information about a specific file.
    Includes a preview of the extracted text content.
    Only returns the file if it belongs to the current department.
    """
    doc = get_document_by_id(file_id, department)
    if not doc:
        raise HTTPException(status_code=404, detail="File not found in your department")

    result = _doc_to_response(doc)
    # Add text preview for the detail view
    full_text = doc.get("extracted_text", "")
    result["extracted_text_preview"] = (
        full_text[:SNIPPET_LENGTH] + "..." if len(full_text) > SNIPPET_LENGTH else full_text
    )
    return result


@router.get("/{file_id}/download")
def download_file(file_id: int, department: str = Depends(get_current_department)):
    """
    Download the original uploaded file.
    Only allows download if the file belongs to the current department.
    """
    doc = get_document_by_id(file_id, department)
    if not doc:
        raise HTTPException(status_code=404, detail="File not found in your department")

    abs_path = get_file_path(doc["filepath"])
    if not abs_path.exists():
        raise HTTPException(status_code=404, detail="Physical file not found on disk")

    return FastAPIFileResponse(
        path=str(abs_path),
        filename=doc["filename"],
        media_type="application/octet-stream",
    )


@router.delete("/{file_id}")
def delete_file_endpoint(file_id: int, department: str = Depends(get_current_department)):
    """
    Delete a file from the system:
    1. Removes the physical file from disk
    2. Deletes the database record (triggers FTS5 index cleanup)
    3. Note: Vector store cleanup happens on next reindex
    """
    doc = get_document_by_id(file_id, department)
    if not doc:
        raise HTTPException(status_code=404, detail="File not found in your department")

    # Delete physical file
    delete_file(doc["filepath"])
    # Delete database record (FTS5 trigger auto-cleans the index)
    deleted = delete_document(file_id, department)

    if deleted:
        return {"message": "File deleted successfully", "success": True}
    return {"message": "File could not be deleted", "success": False}
