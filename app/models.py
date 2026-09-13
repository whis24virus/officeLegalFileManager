"""
Pydantic models (schemas) for Office Legal File Manager.

These define the shape of data flowing through the API:
- Request models: what the client sends to the server
- Response models: what the server sends back to the client

Using Pydantic gives us automatic validation, serialization,
and interactive API documentation at /docs.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# ─── Request Models ─────────────────────────────────────────────

class FileUploadMeta(BaseModel):
    """Metadata submitted alongside a file upload."""
    title: str = Field(..., min_length=1, max_length=200, description="Document title")
    category: str = Field(default="Other", description="File category (Contract, Invoice, etc.)")
    notes: str = Field(default="", max_length=1000, description="Optional notes about the file")


class SearchQuery(BaseModel):
    """Search request parameters."""
    q: str = Field(..., min_length=1, max_length=500, description="Search query text")
    limit: int = Field(default=20, ge=1, le=100, description="Max results to return")


class DepartmentSession(BaseModel):
    """Set current department session (PoC auth)."""
    department: str = Field(..., min_length=1, max_length=100, description="Department name")


class DepartmentCreate(BaseModel):
    """Create a new department."""
    name: str = Field(..., min_length=1, max_length=100, description="Department name")


# ─── Response Models ────────────────────────────────────────────

class FileResponse(BaseModel):
    """Single file/document response."""
    id: int
    title: str
    filename: str
    filetype: str
    filesize: int
    department: str
    category: str
    notes: str
    auto_tags: list[str] = []
    created_at: str
    uploaded_by: str

    class Config:
        from_attributes = True


class FileDetailResponse(FileResponse):
    """Detailed file response including extracted text preview."""
    extracted_text_preview: str = ""  # First N characters of extracted text
    filepath: str = ""


class SearchResultItem(BaseModel):
    """Single search result with relevance info."""
    id: int
    title: str
    filename: str
    filetype: str
    filesize: int
    department: str
    category: str
    auto_tags: list[str] = []
    created_at: str
    snippet: str = ""           # Highlighted text snippet
    relevance_score: float = 0.0  # Combined relevance score (0-1)
    match_source: str = ""      # "keyword", "semantic", or "both"


class SearchResponse(BaseModel):
    """Search results response."""
    query: str
    department: str
    total_results: int
    results: list[SearchResultItem]
    search_time_ms: float


class StatsResponse(BaseModel):
    """System statistics response."""
    total_files: int
    total_departments: int
    departments: list[dict]
    storage_used_bytes: int


class MessageResponse(BaseModel):
    """Generic message response."""
    message: str
    success: bool = True
