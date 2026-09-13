"""
Authentication / Session module for Office Legal File Manager.

For PoC: Simple department-based session using cookies.
The user selects a department from a dropdown, and a session cookie
is set. All subsequent requests read the department from this cookie.

This module provides:
- set_department_cookie(): Sets the department in a response cookie
- get_current_department(): FastAPI dependency that reads department from cookie
- Department validation against known departments

For production, this would be replaced with JWT auth + user-department mapping.
"""

from fastapi import Request, HTTPException, Response
from app.database import get_all_departments


# Cookie name for storing the current department
DEPARTMENT_COOKIE = "olfm_department"


def set_department_cookie(response: Response, department: str):
    """
    Set the department session cookie.
    Cookie is httponly for security (not accessible via JavaScript).
    In PoC, we use a simple cookie. In production, use signed JWT.
    """
    response.set_cookie(
        key=DEPARTMENT_COOKIE,
        value=department.lower(),
        httponly=False,  # Allow JS to read for UI display in PoC
        samesite="lax",
        max_age=86400 * 7  # 7 days
    )


def get_current_department(request: Request) -> str:
    """
    FastAPI dependency: Extract the current department from the session cookie.

    This is injected into every route handler that needs department scoping:
        @router.get("/files")
        def list_files(department: str = Depends(get_current_department)):
            ...

    If no department cookie is set, raises 401 Unauthorized.
    This ensures no API endpoint can accidentally return un-scoped data.
    """
    department = request.cookies.get(DEPARTMENT_COOKIE)
    if not department:
        raise HTTPException(
            status_code=401,
            detail="No department selected. Please select a department first."
        )
    return department.lower()


def validate_department(department: str) -> str:
    """
    Validate that a department exists in the database.
    Returns normalized (lowercase) department name.
    Raises HTTPException if department doesn't exist.
    """
    known = [d.lower() for d in get_all_departments()]
    dept_lower = department.lower()
    if dept_lower not in known:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown department: '{department}'. Known departments: {known}"
        )
    return dept_lower
