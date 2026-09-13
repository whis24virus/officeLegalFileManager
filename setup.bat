@echo off
echo =================================================
echo  Office Legal File Manager - Windows Setup 
echo =================================================

REM Step 1: Check for Python
python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [!] Error: Python is not installed. Please install Python 3.11+.
    pause
    exit /b
)

echo [1/4] Creating Python Virtual Environment...
python -m venv venv

echo [2/4] Activating Virtual Environment and Installing Dependencies...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

echo [3/4] Initializing Database and Default Departments...
python cli.py init
python cli.py add-department Legal
python cli.py add-department HR
python cli.py add-department Finance
python cli.py add-department Operations

echo [4/4] Starting the Server...
echo The application will open at http://localhost:8000
echo Press Ctrl+C to stop the server.
echo =================================================

python main.py
pause
