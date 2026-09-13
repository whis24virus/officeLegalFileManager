import os
import shutil
import tempfile
from pathlib import Path
from unittest import mock

import pytest
from fastapi.testclient import TestClient

# Mock the config paths BEFORE importing the app
temp_dir = tempfile.mkdtemp()
mock_storage = Path(temp_dir) / "storage"
mock_data = Path(temp_dir) / "data"
mock_db = mock_data / "test_app.db"
mock_vectors = mock_data / "vectors"

# We must patch these in app.config before any module imports them
patcher_storage = mock.patch("app.config.STORAGE_DIR", mock_storage)
patcher_data = mock.patch("app.config.DATA_DIR", mock_data)
patcher_db = mock.patch("app.config.DB_PATH", mock_db)
patcher_vectors = mock.patch("app.config.VECTORS_DIR", mock_vectors)

patcher_storage.start()
patcher_data.start()
patcher_db.start()
patcher_vectors.start()

from app.config import ensure_directories
from app.database import init_db, get_connection
from main import app

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Create temp directories and initialize test database."""
    ensure_directories()
    init_db()
    yield
    # Teardown
    shutil.rmtree(temp_dir, ignore_errors=True)

@pytest.fixture
def client():
    """Returns a FastAPI TestClient."""
    with TestClient(app) as c:
        yield c

@pytest.fixture
def db_conn():
    """Returns a direct database connection."""
    conn = get_connection()
    yield conn
    conn.close()

@pytest.fixture
def clean_db(db_conn):
    """Cleans all documents from the database before a test."""
    db_conn.execute("DELETE FROM documents")
    db_conn.execute("DELETE FROM documents_fts")
    db_conn.commit()
    yield db_conn
