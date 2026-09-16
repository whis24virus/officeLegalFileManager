"""
Database module for Office Legal File Manager.

Manages SQLite database with FTS5 (Full-Text Search) virtual table.
All document metadata, extracted text, and auto-tags are stored here.

Key Design Decisions:
- SQLite is used because it's built into Python (zero setup).
- FTS5 virtual table enables sub-millisecond full-text keyword search.
- Department field is present in every query for hard isolation.
- The FTS5 table is kept in sync with the documents table via triggers.
"""

import sqlite3
import json
from pathlib import Path
from typing import Optional
from app.config import DB_PATH, DEFAULT_DEPARTMENTS, ensure_directories


def get_connection() -> sqlite3.Connection:
    """
    Get a SQLite connection with optimized settings.
    Returns a connection with Row factory for dict-like access.
    """
    ensure_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for better concurrent read performance
    conn.execute("PRAGMA journal_mode=WAL")
    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """
    Initialize the database schema.
    Creates tables, FTS5 virtual table, and seeds default departments.
    Safe to call multiple times (uses IF NOT EXISTS).
    """
    conn = get_connection()
    cursor = conn.cursor()

    # ─── Departments Table ──────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS departments (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    """)

    # ─── Documents Table ────────────────────────────────────────
    # This is the main table storing all file metadata and extracted content.
    # 'department' is the hard isolation key — every query filters on it.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            title           TEXT NOT NULL,
            filename        TEXT NOT NULL,
            filepath        TEXT NOT NULL,
            filetype        TEXT NOT NULL,
            filesize        INTEGER NOT NULL,
            department      TEXT NOT NULL,
            category        TEXT DEFAULT 'Other',
            notes           TEXT DEFAULT '',
            auto_tags       TEXT DEFAULT '[]',
            extracted_text  TEXT DEFAULT '',
            embedding_id    INTEGER DEFAULT -1,
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
            uploaded_by     TEXT DEFAULT 'system'
        )
    """)

    # Index on department for fast filtered queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_documents_department
        ON documents(department)
    """)

    # ─── FTS5 Virtual Table ─────────────────────────────────────
    # FTS5 (Full-Text Search 5) is SQLite's built-in search engine.
    # It creates an inverted index over the specified columns,
    # enabling sub-millisecond keyword searches.
    #
    # content='documents' means FTS5 reads from the documents table.
    # content_rowid='id' maps FTS rows to document IDs.
    #
    # We index: title, extracted_text, auto_tags, notes
    # Department is NOT in FTS — we filter by it in the JOIN query.
    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
            title,
            extracted_text,
            auto_tags,
            notes,
            content='documents',
            content_rowid='id'
        )
    """)

    # ─── FTS Sync Triggers ──────────────────────────────────────
    # These triggers keep the FTS5 index in sync with the documents table.
    # When a document is inserted, updated, or deleted, the FTS index
    # is automatically updated.

    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
            INSERT INTO documents_fts(rowid, title, extracted_text, auto_tags, notes)
            VALUES (new.id, new.title, new.extracted_text, new.auto_tags, new.notes);
        END
    """)

    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
            INSERT INTO documents_fts(documents_fts, rowid, title, extracted_text, auto_tags, notes)
            VALUES ('delete', old.id, old.title, old.extracted_text, old.auto_tags, old.notes);
        END
    """)

    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS documents_au AFTER UPDATE ON documents BEGIN
            INSERT INTO documents_fts(documents_fts, rowid, title, extracted_text, auto_tags, notes)
            VALUES ('delete', old.id, old.title, old.extracted_text, old.auto_tags, old.notes);
            INSERT INTO documents_fts(rowid, title, extracted_text, auto_tags, notes)
            VALUES (new.id, new.title, new.extracted_text, new.auto_tags, new.notes);
        END
    """)

    # ─── Seed Default Departments ───────────────────────────────
    for dept in DEFAULT_DEPARTMENTS:
        cursor.execute(
            "INSERT OR IGNORE INTO departments (name) VALUES (?)",
            (dept,)
        )

    conn.commit()

    # ─── V3: Migration — Add summary column if not present ──────
    try:
        cursor.execute("ALTER TABLE documents ADD COLUMN summary TEXT DEFAULT ''")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists — safe to ignore

    conn.close()


# ─── CRUD Operations ───────────────────────────────────────────

def insert_document(
    title: str,
    filename: str,
    filepath: str,
    filetype: str,
    filesize: int,
    department: str,
    category: str = "Other",
    notes: str = "",
    auto_tags: list = None,
    extracted_text: str = "",
    embedding_id: int = -1,
    uploaded_by: str = "system"
) -> int:
    """
    Insert a new document record. Returns the new document ID.
    The FTS5 index is automatically updated via the trigger.
    """
    if auto_tags is None:
        auto_tags = []

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO documents
            (title, filename, filepath, filetype, filesize, department,
             category, notes, auto_tags, extracted_text, embedding_id, uploaded_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        title, filename, filepath, filetype, filesize, department.lower(),
        category, notes, json.dumps(auto_tags), extracted_text,
        embedding_id, uploaded_by
    ))
    doc_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return doc_id


def update_document_tags_and_embedding(doc_id: int, auto_tags: list, embedding_id: int):
    """
    Update auto-tags and embedding ID after async processing completes.
    Triggers FTS5 re-index automatically.
    """
    conn = get_connection()
    conn.execute(
        "UPDATE documents SET auto_tags = ?, embedding_id = ? WHERE id = ?",
        (json.dumps(auto_tags), embedding_id, doc_id)
    )
    conn.commit()
    conn.close()

def update_document_text_tags_embedding(doc_id: int, extracted_text: str, auto_tags: list, embedding_id: int):
    """
    Update text, auto-tags, and embedding ID after async extraction completes.
    Triggers FTS5 re-index automatically.
    """
    conn = get_connection()
    conn.execute(
        "UPDATE documents SET extracted_text = ?, auto_tags = ?, embedding_id = ? WHERE id = ?",
        (extracted_text, json.dumps(auto_tags), embedding_id, doc_id)
    )
    conn.commit()
    conn.close()


def get_documents_by_department(department: str, limit: int = 100, offset: int = 0) -> list:
    """Get all documents for a specific department. Hard-scoped query."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT * FROM documents
           WHERE department = ?
           ORDER BY created_at DESC
           LIMIT ? OFFSET ?""",
        (department.lower(), limit, offset)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_document_by_id(doc_id: int, department: str) -> Optional[dict]:
    """
    Get a single document by ID, but ONLY if it belongs to the given department.
    This prevents cross-department access even if someone guesses an ID.
    """
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM documents WHERE id = ? AND department = ?",
        (doc_id, department.lower())
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_document(doc_id: int, department: str) -> bool:
    """
    Delete a document, but ONLY if it belongs to the given department.
    FTS5 index is auto-updated via the delete trigger.
    Returns True if a row was deleted.
    """
    conn = get_connection()
    cursor = conn.execute(
        "DELETE FROM documents WHERE id = ? AND department = ?",
        (doc_id, department.lower())
    )
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def update_document_summary(doc_id: int, summary: str) -> None:
    """Store a pre-computed LLM summary for a document."""
    conn = get_connection()
    conn.execute(
        "UPDATE documents SET summary = ? WHERE id = ?",
        (summary, doc_id)
    )
    conn.commit()
    conn.close()


def get_document_summary(doc_id: int) -> str:
    """Retrieve the pre-computed summary for a document."""
    conn = get_connection()
    row = conn.execute(
        "SELECT summary FROM documents WHERE id = ?",
        (doc_id,)
    ).fetchone()
    conn.close()
    return row["summary"] if row and row["summary"] else ""


def search_fts(query: str, department: str, limit: int = 20) -> list:
    """
    Full-text keyword search using SQLite FTS5.

    HOW IT WORKS:
    1. FTS5 has an inverted index mapping every word → list of document IDs.
    2. The MATCH operator searches this index in sub-millisecond time.
    3. bm25() calculates relevance score (like Google's ranking algorithm).
    4. The JOIN with documents table filters by department FIRST,
       so FTS5 never even considers documents from other departments.

    The rank column from bm25() is negative (more negative = more relevant),
    so we ORDER BY rank ASC.
    """
    conn = get_connection()

    # Sanitize query for FTS5: wrap each word in quotes to handle special chars
    # and join with spaces for implicit AND matching
    words = query.strip().split()
    if not words:
        conn.close()
        return []

    # Build FTS5 query: each word as a separate token with a wildcard for prefix matching
    fts_query = " ".join(f'"{w}"*' for w in words)

    rows = conn.execute("""
        SELECT d.*, bm25(documents_fts) as rank
        FROM documents_fts fts
        JOIN documents d ON d.id = fts.rowid
        WHERE documents_fts MATCH ?
          AND d.department = ?
        ORDER BY rank
        LIMIT ?
    """, (fts_query, department.lower(), limit)).fetchall()

    conn.close()
    return [dict(row) for row in rows]


def get_all_departments() -> list:
    """Get list of all department names."""
    conn = get_connection()
    rows = conn.execute("SELECT name FROM departments ORDER BY name").fetchall()
    conn.close()
    return [row["name"] for row in rows]


def add_department(name: str) -> bool:
    """Add a new department. Returns False if it already exists."""
    conn = get_connection()
    try:
        conn.execute("INSERT INTO departments (name) VALUES (?)", (name,))
        # Create storage directory for the new department
        from app.config import STORAGE_DIR
        (STORAGE_DIR / name.lower()).mkdir(parents=True, exist_ok=True)
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False


def get_department_stats() -> list:
    """Get file count per department for admin stats."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT department, COUNT(*) as file_count,
               SUM(filesize) as total_size
        FROM documents
        GROUP BY department
    """).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_total_file_count() -> int:
    """Get total number of files across all departments."""
    conn = get_connection()
    row = conn.execute("SELECT COUNT(*) as cnt FROM documents").fetchone()
    conn.close()
    return row["cnt"]


def get_all_documents_in_department(department: str) -> list:
    """Get ALL documents for a department (used for reindexing)."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM documents WHERE department = ? ORDER BY id",
        (department.lower(),)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_department_vocabulary(department: str) -> set:
    """
    Scan all auto_tags and extracted_text in a department to build a custom dictionary/vocabulary.
    Used for 'Did you mean?' spell correction and autocomplete.
    """
    conn = get_connection()
    rows = conn.execute(
        "SELECT auto_tags, extracted_text FROM documents WHERE department = ?",
        (department.lower(),)
    ).fetchall()
    conn.close()
    
    vocab = set()
    for row in rows:
        # Process tags
        try:
            tags = json.loads(row["auto_tags"])
            for tag in tags:
                for word in str(tag).split():
                    clean_word = "".join(c for c in word.lower() if c.isalnum())
                    if len(clean_word) > 2:
                        vocab.add(clean_word)
        except (json.JSONDecodeError, TypeError):
            pass
            
        # Process extracted text
        text = row["extracted_text"]
        if text:
            for word in text.split():
                clean_word = "".join(c for c in word.lower() if c.isalnum())
                if len(clean_word) > 2:
                    vocab.add(clean_word)
                    
    return vocab
