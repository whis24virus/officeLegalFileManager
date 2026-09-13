import pytest
from app.database import add_department, get_all_departments, insert_document, get_documents_by_department, delete_document

def test_add_and_get_departments(clean_db):
    depts = get_all_departments()
    # Conftest already seeded default departments, so length should be > 0
    assert "Legal" in depts
    
    add_department("Testing")
    depts_new = get_all_departments()
    assert "Testing" in depts_new

def test_insert_and_get_document(clean_db):
    doc_id = insert_document(
        title="Test Doc",
        filename="test.txt",
        filepath="legal/test.txt",
        filetype="txt",
        filesize=100,
        department="legal",
        category="Contract",
        notes="A test document",
        extracted_text="Hello world",
        auto_tags="test, hello",
        uploaded_by="user1"
    )
    
    assert doc_id > 0
    
    docs = get_documents_by_department("legal")
    assert len(docs) == 1
    assert docs[0]["title"] == "Test Doc"
    assert docs[0]["filename"] == "test.txt"

def test_department_isolation(clean_db):
    insert_document(
        title="Legal Doc",
        filename="legal.txt",
        filepath="legal/legal.txt",
        filetype="txt",
        filesize=100,
        department="legal",
        category="Contract",
    )
    insert_document(
        title="HR Doc",
        filename="hr.txt",
        filepath="hr/hr.txt",
        filetype="txt",
        filesize=100,
        department="hr",
        category="Memo",
    )
    
    legal_docs = get_documents_by_department("legal")
    assert len(legal_docs) == 1
    assert legal_docs[0]["title"] == "Legal Doc"
    
    hr_docs = get_documents_by_department("hr")
    assert len(hr_docs) == 1
    assert hr_docs[0]["title"] == "HR Doc"

def test_delete_document(clean_db):
    doc_id = insert_document(
        title="To Delete",
        filename="del.txt",
        filepath="legal/del.txt",
        filetype="txt",
        filesize=100,
        department="legal",
        category="Contract",
    )
    
    assert len(get_documents_by_department("legal")) == 1
    success = delete_document(doc_id, department="legal")
    assert success is True
    assert len(get_documents_by_department("legal")) == 0
