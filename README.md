# Office Legal File Manager

A robust Proof of Concept (PoC) document management system designed to securely store, auto-tag, and intelligently search legal and corporate files across isolated department workspaces. It utilizes an advanced hybrid search engine (Full-Text Search + Semantic Vector Search) to deliver highly accurate document retrieval.

## Prerequisites

*   **Python 3.11+**
*   **Tesseract OCR**: Required for image-to-text extraction.
    *   macOS: `brew install tesseract`
    *   Linux: `sudo apt-get install tesseract-ocr`
    *   Windows: Download from UB-Mannheim

## 1. Quick Start Installation

### 🚀 The One-Click Setup (Recommended)
I have created a fully automated setup script for you. It will create the Python environment, download all AI models, set up the database, and launch the server for you in a single command.

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-org/officeLegalFileManager.git
   cd officeLegalFileManager
   ```

2. **Run the script for your Operating System:**
   * **macOS / Linux:**
     ```bash
     chmod +x setup.sh
     ./setup.sh
     ```
   * **Windows:**
     ```cmd
     setup.bat
     ```

### 🛠️ Manual Setup
If you prefer to set up the environment manually step-by-step:

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-org/officeLegalFileManager.git
    cd officeLegalFileManager
    ```

2.  **Create a virtual environment and install dependencies:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    pip install -r requirements.txt
    ```

3.  **Initialize the application:**
    This command will create the necessary storage directories and set up the SQLite database.
    ```bash
    python cli.py init
    ```

4.  **Create your first department:**
    ```bash
    python cli.py add-department Legal
    python cli.py add-department HR
    ```

## 2. Tooling & Technologies Explained

Here is a breakdown of every core tool powering this application, why it exists, and what version is recommended.

| Tool | Version | Role in Application | Plain English Explanation |
| :--- | :--- | :--- | :--- |
| **Python** | `3.11+` | Core Programming Language | The engine that runs all backend logic, API routes, and artificial intelligence models. |
| **FastAPI** | `0.104+` | Web Server Framework | Creates the API endpoints (like `/api/upload`) and serves the web pages to your browser blazingly fast. |
| **SQLite (FTS5)** | Built-in | Database & Exact Search | A lightweight database that stores document metadata and provides ultra-fast exact keyword searching using its "FTS5" (Full-Text Search) module. |
| **Sentence-Transformers** | `2.2+` | Artificial Intelligence Model | A neural network by HuggingFace that reads your text and turns it into math (vectors), allowing the system to understand the *meaning* of words, not just the spelling. |
| **NumPy** | `1.26+` | Math Engine | Quickly calculates the mathematical distance between vectors to figure out which documents are semantically similar to your search query. |
| **PyPDF2 / pdfplumber** | `3.0+` | Text Extractor | Reads the raw text hidden inside PDF files. |
| **Tesseract OCR** | `5.3+` | Image Scanner (External) | "Optical Character Recognition." It looks at scanned images or picture-based PDFs and magically converts the images of words into real text. |

## 3. Complete User Journey Flow

**Scenario:** *You are a lawyer trying to find a specific clause about supplier terminations.*

1. **The Setup:** You open `http://localhost:8000` and type `Legal` to enter your isolated department workspace.
2. **The Upload:** You drag and drop a 50-page scanned PDF called `Acme_Corp_Contract.pdf` into the upload box.
3. **The Backend Magic (Async processing):**
   * The server instantly accepts the file and saves it to the `storage/legal/` folder.
   * In the background, `Tesseract OCR` reads the scanned images and converts them to text.
   * The `Tagger` scans the text and automatically assigns tags like `contract`, `termination`, and `liability`.
   * The `Embedder` (MiniLM) reads the text and turns the meaning of the document into a 384-dimensional mathematical vector, saving it to `vectors/legal/vectors.npy`.
4. **The Search:** You type `"how to cancel vendor agreement"` into the search bar.
   * **Exact Search:** SQLite looks for those exact words. It fails, because the document actually says "Supplier Termination Clause".
   * **Semantic Search:** The AI converts your query into math, compares it against the saved vectors using `NumPy`, and realizes that "cancel vendor agreement" means the exact same thing as "supplier termination".
5. **The Result:** The UI instantly presents the `Acme_Corp_Contract.pdf` with a high relevance score, highlighting the matching keywords!

## 4. Usage

### Running the Web Server
Launch the FastAPI backend server:
```bash
python main.py
```
The web interface will be available at `http://localhost:8000`.

### 📱 Running on your iPhone (For Demonstration)
If you want to view the app on your phone while it runs on your computer:
1. Ensure your iPhone and Computer are on the **same Wi-Fi network**.
2. Find your computer's Local IP Address (e.g., `192.168.1.15`).
   - Mac: `System Settings -> Network -> Wi-Fi -> Details`
   - Windows: Run `ipconfig` in CMD and look for `IPv4 Address`.
3. Open Safari on your iPhone and go to: `http://192.168.1.15:8000` (Replace with your actual IP).

*   **Login Page**: Enter your designated department (e.g., "Legal") to enter your isolated workspace.
*   **Dashboard**: View your uploaded files, system statistics, and tags.
*   **Search**: Use the global search bar to perform semantic hybrid searches (e.g., search "contract termination" to find "Lease Cancellation Agreement").

### Using the CLI Admin Tool

The CLI provides powerful administrative controls directly from the terminal.

*   **View System Stats:**
    ```bash
    python cli.py stats
    ```
*   **Upload a File:**
    ```bash
    python cli.py upload --file ./sample_contract.pdf --department Legal --title "Q3 Supplier Contract"
    ```
*   **Search via Terminal:**
    ```bash
    python cli.py search --department Legal --query "confidentiality clause"
    ```
*   **Rebuild Search Indexes:**
    ```bash
    python cli.py reindex
    ```

## 5. Free Deployment & Hosting Guide

If you want to host this application on the internet for free, here are your best options.

### 🌐 Option A: Render.com (Highly Recommended, Free Tier)
Render offers free web services that can easily run FastAPI.
1. Push your code to a **GitHub** repository.
2. Sign up at [Render.com](https://render.com) and click **New -> Web Service**.
3. Connect your GitHub account and select your repository.
4. Set the Start Command to: `uvicorn main:app --host 0.0.0.0 --port 10000`
5. *Note:* Render's free tier spins down after 15 minutes of inactivity, so the first request after a break might take 30 seconds to load.

### 🌐 Option B: Railway.app or PythonAnywhere
* **Railway:** Similar to Render, very easy GitHub integration. Provides a small free tier allowance every month.
* **PythonAnywhere:** Great for pure Python apps, but they do not support heavy AI models (like PyTorch) on the free tier.

### 💾 What about GitHub Pages?
**No.** GitHub Pages is only for "Static" websites (pure HTML/CSS). Because this application requires a Python backend server, SQLite database, and Artificial Intelligence models to process documents, it **cannot** be hosted on GitHub Pages. You must use a service like Render that provides a virtual server to run Python.

## 6. Project Structure

```text
officeLegalFileManager/
├── app/
│   ├── main.py            # FastAPI Application Entrypoint
│   ├── config.py          # Centralized configuration variables
│   ├── database.py        # SQLite + FTS5 logic
│   ├── models.py          # Pydantic data schemas
│   ├── auth.py            # Department-level session auth
│   └── services/
│       ├── extractor.py   # PDF/DOCX/OCR text extraction
│       ├── tagger.py      # TF-IDF / RAKE auto-tagging
│       ├── embedder.py    # Semantic sentence-transformers
│       └── storage.py     # File I/O operations
├── docs/
│   └── ARCHITECTURE.md    # Comprehensive system design documentation
├── cli.py                 # Admin Command Line Interface
├── requirements.txt
└── README.md
```

## Tech Stack

| Component | Technology | Description |
| :--- | :--- | :--- |
| **Backend** | FastAPI | High-performance async web framework |
| **CLI Framework** | Click & Rich | Argument parsing and terminal UI formatting |
| **Database** | SQLite + FTS5 | Zero-config SQL store with fast Full-Text Search |
| **AI / NLP** | sentence-transformers | Generates 384D semantic embeddings (MiniLM) |
| **Text Parsing** | pdfplumber, python-docx | High-fidelity text extraction |
| **OCR** | pytesseract | Image-to-text for scanned documents |

## License
MIT License
