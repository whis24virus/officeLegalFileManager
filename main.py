"""
Office Legal File Manager — Main Application Entry Point

This is the FastAPI application that ties everything together:
- Serves the web UI (static HTML/CSS/JS files)
- Mounts API routers for file management and search
- Provides session management (department selection)
- Initializes the database on startup

Run with:
    python main.py
Then open http://localhost:8000 in your browser.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
import uvicorn

from app.config import (
    ensure_directories,
    DEBUG,
    HOST,
    PORT,
    DEFAULT_DEPARTMENTS,
    FILE_CATEGORIES,
)
from app.database import init_db, get_all_departments, add_department
from app.auth import set_department_cookie
from app.routers import files, search, rag

# ─── Logging Setup ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ─── Application Lifespan ──────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup and shutdown logic for the FastAPI application.
    On startup:
    - Create required directories (storage, data, vectors)
    - Initialize SQLite database and FTS5 indexes
    - Seed default departments if they don't exist
    """
    logger.info("🚀 Starting Office Legal File Manager...")
    ensure_directories()
    init_db()

    # Seed default departments
    existing_depts = get_all_departments()  # Returns list of strings
    for dept in DEFAULT_DEPARTMENTS:
        if dept not in existing_depts:
            add_department(dept)
            logger.info(f"  ✅ Created department: {dept}")

    logger.info(f"📂 Departments: {get_all_departments()}")

    # ── V3: Preload AI models into memory during boot ──
    from app.services.embedder import embedder_service
    from app.services.llm import llm_service
    logger.info("🧠 Preloading Embedding model (BGE-Large)...")
    embedder_service._load_model()
    logger.info("🤖 Preloading LLM model (Flan-T5)...")
    llm_service._load_model()
    logger.info("🔀 Preloading Cross-Encoder Re-Ranker...")
    from app.services.reranker import reranker_service
    reranker_service._load_model()
    logger.info("✅ All AI models loaded and ready!")

    logger.info(f"🌐 Server ready at http://localhost:{PORT}")
    yield
    logger.info("👋 Shutting down Office Legal File Manager.")


# ─── FastAPI App ────────────────────────────────────────────────
app = FastAPI(
    title="Office Legal File Manager",
    description="Multi-department document management with hybrid semantic search",
    version="1.0.0",
    lifespan=lifespan,
)

# ─── Static Files (Frontend UI) ────────────────────────────────
static_dir = os.path.join(os.path.dirname(__file__), "app", "static")
os.makedirs(static_dir, exist_ok=True)

# ─── Include API Routers ───────────────────────────────────────
app.include_router(files.router, prefix="/api/files")
app.include_router(search.router, prefix="/api")
app.include_router(rag.router, prefix="/api")


# ─── Root: Serve the SPA ───────────────────────────────────────
# Will be mounted at the end of the file


# ─── Session Endpoint ──────────────────────────────────────────
from pydantic import BaseModel


class DepartmentRequest(BaseModel):
    department: str


@app.post("/api/session")
async def create_session(request: DepartmentRequest, response: Response):
    """
    Set the department session cookie.
    Called when a user selects their department from the dropdown.
    The cookie is then read by get_current_department() in all scoped endpoints.
    """
    dept_name = request.department.strip()
    if not dept_name:
        return {"message": "Department name is required", "success": False}

    # Validate department exists
    known = get_all_departments()
    known_lower = [d.lower() for d in known]
    if dept_name.lower() not in known_lower:
        return {"message": f"Unknown department: {dept_name}", "success": False}

    set_department_cookie(response, dept_name)
    return {"message": f"Session set for department: {dept_name}", "success": True}


# ─── Department & Category Endpoints ───────────────────────────
@app.get("/api/departments")
async def list_departments():
    """List all available departments. Used by frontend department selector."""
    return get_all_departments()


@app.get("/api/categories")
async def list_categories():
    """List all available file categories. Used by frontend upload form."""
    return FILE_CATEGORIES


# ─── Root: Serve the SPA ───────────────────────────────────────
# Mounted at the very end to prevent intercepting /api/ routes
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")


# ─── Run Server ─────────────────────────────────────────────────
if __name__ == "__main__":
        uvicorn.run(
            "main:app",
            host=HOST,
            port=PORT,
            reload=DEBUG,
            reload_excludes=["data/*", "storage/*", "vectors/*", "*.db", "*.db-*", "*.npy", "*.json"],
        )
