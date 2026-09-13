import pytest
import io

def test_list_departments(client):
    response = client.get("/api/departments")
    assert response.status_code == 200
    assert "Legal" in response.json()

def test_list_categories(client):
    response = client.get("/api/categories")
    assert response.status_code == 200
    assert "Contract" in response.json()

def test_create_session(client):
    response = client.post("/api/session", json={"department": "legal"})
    assert response.status_code == 200
    assert response.json()["success"] is True
    # Verify cookie was set
    assert "olfm_department" in response.cookies
    assert response.cookies["olfm_department"] == "legal"

def test_files_unauthorized_without_cookie(client):
    # Do not set cookie
    response = client.get("/api/files/")
    assert response.status_code == 401

def test_files_authorized_with_cookie(client):
    client.post("/api/session", json={"department": "legal"})
    response = client.get("/api/files/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_file_upload(client):
    client.post("/api/session", json={"department": "legal"})
    file_content = b"This is a test document about non-disclosure agreements."
    files = {"file": ("test_nda.txt", file_content, "text/plain")}
    data = {"title": "Test NDA", "category": "Contract", "notes": "Test"}
    
    response = client.post("/api/files/upload", files=files, data=data)
    assert response.status_code == 200
    result = response.json()
    assert result["filename"] == "test_nda.txt"
    assert result["department"] == "legal"
    
    # Check that it appears in files list
    list_resp = client.get("/api/files/")
    docs = list_resp.json()
    assert len(docs) >= 1
    assert any(d["filename"] == "test_nda.txt" for d in docs)

def test_search_api(client, clean_db):
    client.post("/api/session", json={"department": "legal"})
    
    # Upload a document to search
    file_content = b"Confidential memo regarding project X."
    files = {"file": ("memo.txt", file_content, "text/plain")}
    data = {"title": "Project Memo", "category": "Memo", "notes": ""}
    client.post("/api/files/upload", files=files, data=data)
    
    # Perform search
    response = client.get("/api/search?q=Confidential")
    assert response.status_code == 200
    data = response.json()
    assert len(data["exact_matches"]) >= 1
    assert "memo.txt" in [r["filename"] for r in data["exact_matches"]]
