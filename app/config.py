"""
Configuration settings for Office Legal File Manager.

All paths are relative to the project root directory.
No environment variables or external config files needed for PoC.
"""

import os
from pathlib import Path


# ─── Project Root ───────────────────────────────────────────────
# Automatically resolves to the directory containing this config file's parent
PROJECT_ROOT = Path(__file__).parent.parent.resolve()

# ─── Storage Paths ──────────────────────────────────────────────
# Where uploaded files are physically stored, organized by department
STORAGE_DIR = PROJECT_ROOT / "storage"

# Where SQLite database and vector index files live
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "app.db"
VECTORS_DIR = DATA_DIR / "vectors"

# ─── Upload Constraints ────────────────────────────────────────
MAX_FILE_SIZE_MB = 50
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024  # 50 MB

# Supported file extensions (lowercase, with dot)
ALLOWED_EXTENSIONS = {
    ".pdf", ".txt", ".doc", ".docx",
    ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp",
    ".xlsx", ".xls", ".csv",
    ".eml", ".msg"
}

# File types that need OCR (image files)
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp"}

# File types that are documents (text-extractable)
DOCUMENT_EXTENSIONS = {
    ".pdf", ".txt", ".doc", ".docx",
    ".xlsx", ".xls", ".csv",
    ".eml", ".msg"
}

# ─── Default Departments ───────────────────────────────────────
DEFAULT_DEPARTMENTS = ["Legal", "HR", "Finance", "Operations"]

# ─── Default File Categories ───────────────────────────────────
FILE_CATEGORIES = [
    "Contract", "Invoice", "Memo", "Report",
    "Letter", "Policy", "Other"
]

# ─── V2/V4: AI Services Settings ─────────────────────────────────
EMBEDDING_MODEL_NAME = "BAAI/bge-large-en-v1.5"
EMBEDDING_DIMENSION = 1024  # Output vector size for this model
LLM_MODEL_NAME = "google/flan-t5-large"  # Upgraded in V4 for better logical filtering (~3GB RAM)

# ─── Auto-Tagging Settings ─────────────────────────────────────
MAX_AUTO_TAGS = 10          # Maximum number of auto-generated tags per file
MIN_TAG_LENGTH = 3          # Minimum character length for a tag
MAX_TAG_LENGTH = 50         # Maximum character length for a tag

# ─── Search Settings ───────────────────────────────────────────
SEARCH_RESULTS_LIMIT = 20          # Max results returned per search
FTS_WEIGHT = 0.7                   # Weight for keyword (FTS5) results (boosted to favor exact matches)
SEMANTIC_WEIGHT = 0.3              # Weight for semantic (vector) results
SNIPPET_LENGTH = 200               # Characters of text snippet in results

# ─── V3: Chunk-Level Embedding Settings ────────────────────────
CHUNK_SIZE = 500                   # Target characters per chunk
CHUNK_OVERLAP = 50                 # Overlap characters between chunks

# ─── V3: Cross-Encoder Re-Ranking ──────────────────────────────
RERANKER_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"  # ~80MB, fast
RERANK_TOP_K = 20                  # Number of candidates to re-rank

# ─── Server Settings ───────────────────────────────────────────
HOST = "0.0.0.0"
PORT = 8000
DEBUG = True

# ─── Tesseract OCR ─────────────────────────────────────────────
# Path to tesseract binary. Usually auto-detected.
# Override if tesseract is installed in a non-standard location.
TESSERACT_CMD = os.getenv("TESSERACT_CMD", "tesseract")

# ─── Ensure directories exist ──────────────────────────────────
def ensure_directories():
    """Create all required directories if they don't exist."""
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    VECTORS_DIR.mkdir(parents=True, exist_ok=True)
    for dept in DEFAULT_DEPARTMENTS:
        (STORAGE_DIR / dept.lower()).mkdir(parents=True, exist_ok=True)
