import logging
import uuid
import os
from pathlib import Path

from app.config import STORAGE_DIR

logger = logging.getLogger(__name__)

def save_file(file_data: bytes, department: str, original_filename: str) -> tuple[str, int]:
    """
    Saves a file to the filesystem under a department-specific directory,
    using a UUID-based filename to avoid collisions.
    
    Args:
        file_data (bytes): The binary data of the file.
        department (str): The department name.
        original_filename (str): The original name of the file to extract extension.
        
    Returns:
        tuple[str, int]: A tuple containing the relative file path and file size in bytes.
    """
    ext = os.path.splitext(original_filename)[1]
    new_filename = f"{uuid.uuid4()}{ext}"
    
    dept_dir = Path(STORAGE_DIR) / department
    dept_dir.mkdir(parents=True, exist_ok=True)
    
    filepath = dept_dir / new_filename
    
    with open(filepath, 'wb') as f:
        f.write(file_data)
        
    filesize = len(file_data)
    rel_path = f"{department}/{new_filename}"
    return rel_path, filesize

def delete_file(filepath: str) -> bool:
    """
    Deletes a file from the filesystem given its relative path.
    """
    full_path = Path(STORAGE_DIR) / filepath
    try:
        if full_path.exists():
            full_path.unlink()
            return True
    except Exception as e:
        logger.error(f"Failed to delete file {filepath}: {e}")
    return False

def get_file_path(filepath: str) -> Path:
    """
    Returns the absolute Path object for a given relative filepath.
    """
    return Path(STORAGE_DIR) / filepath
