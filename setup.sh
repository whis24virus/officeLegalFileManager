#!/bin/bash
# One-Click Setup & Run Script for macOS / Linux

echo "================================================="
echo "⚖️  Office Legal File Manager - macOS/Linux Setup ⚖️"
echo "================================================="

# Step 1: Check for Python
if ! command -v python3 &> /dev/null; then
    echo "[!] Error: Python3 is not installed. Please install Python 3.11+."
    exit 1
fi

echo "[1/4] Creating Python Virtual Environment..."
python3 -m venv venv

echo "[2/4] Activating Virtual Environment and Installing Dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "[3/4] Initializing Database and Default Departments..."
python cli.py init
python cli.py add-department Legal
python cli.py add-department HR
python cli.py add-department Finance
python cli.py add-department Operations

echo "[4/4] Starting the Server..."
echo "🚀 The application will open at http://localhost:8000"
echo "Press Ctrl+C to stop the server."
echo "================================================="

python main.py
