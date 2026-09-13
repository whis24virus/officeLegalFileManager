"""
Office Legal File Manager — CLI Admin Tool

A command-line interface for administrative tasks:
  stats, add-department, list-departments, list-files,
  reindex, delete-file, upload, search, init

Usage:
    python cli.py stats
    python cli.py list-files --department legal
    python cli.py upload --file ./doc.pdf --department legal --title "My Doc"
    python cli.py search --department legal --query "lease agreement"
"""

import json
import math
import os
import sys

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
from rich.prompt import Confirm

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.config import ensure_directories, STORAGE_DIR
from app.database import (
    init_db,
    get_total_file_count,
    get_all_departments,
    get_department_stats,
    add_department as db_add_department,
    get_documents_by_department,
    delete_document,
    get_document_by_id,
    search_fts,
    get_all_documents_in_department,
    update_document_tags_and_embedding,
    insert_document,
)
from app.services.storage import save_file, delete_file, get_file_path
from app.services.extractor import extract_text
from app.services.tagger import generate_tags
from app.services.embedder import EmbeddingService

console = Console()
_embedder = None


def get_embedder():
    """Lazy-load the embedding service (avoids loading MiniLM on every CLI call)."""
    global _embedder
    if _embedder is None:
        _embedder = EmbeddingService()
    return _embedder


def format_size(size_bytes):
    """Format bytes into human-readable string."""
    if not size_bytes or size_bytes == 0:
        return "0 B"
    size_names = ("B", "KB", "MB", "GB", "TB")
    i = int(math.floor(math.log(max(size_bytes, 1), 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_names[i]}"


def parse_tags(raw):
    """Parse auto_tags from JSON string or list."""
    if isinstance(raw, list):
        return raw
    try:
        return json.loads(raw) if raw else []
    except (json.JSONDecodeError, TypeError):
        return []


# ─── CLI Group ──────────────────────────────────────────────────
@click.group()
def cli():
    """Office Legal File Manager — Admin CLI"""
    pass


# ─── init ───────────────────────────────────────────────────────
@cli.command()
def init():
    """Initialize database and create directories."""
    ensure_directories()
    init_db()
    console.print(Panel(
        "[bold green]✅ Initialization Complete![/bold green]\n"
        "Database and directories are ready.",
        title="Office Legal File Manager"
    ))


# ─── stats ──────────────────────────────────────────────────────
@cli.command()
def stats():
    """Show system-wide statistics."""
    ensure_directories()
    init_db()

    total_files = get_total_file_count()
    depts = get_all_departments()  # Returns list of strings: ["Finance", "HR", ...]
    dept_stats = get_department_stats()  # Returns list of dicts: [{"department": "legal", "file_count": 5, "total_size": 12345}, ...]

    # Summary panel
    summary_table = Table(title="📊 System Statistics", show_header=True)
    summary_table.add_column("Metric", style="cyan", min_width=20)
    summary_table.add_column("Value", style="magenta", justify="right")
    summary_table.add_row("Total Files", str(total_files))
    summary_table.add_row("Total Departments", str(len(depts)))

    # Calculate total storage
    total_storage = sum(s.get("total_size", 0) or 0 for s in dept_stats)
    summary_table.add_row("Storage Used", format_size(total_storage))
    console.print(summary_table)

    # Per-department breakdown
    if depts:
        dept_table = Table(title="📂 Department Breakdown", show_header=True)
        dept_table.add_column("Department", style="cyan")
        dept_table.add_column("Files", justify="right", style="green")
        dept_table.add_column("Storage", justify="right", style="yellow")

        # Build a lookup from dept_stats
        stats_lookup = {s["department"]: s for s in dept_stats}

        for dept_name in depts:
            s = stats_lookup.get(dept_name.lower(), {})
            count = s.get("file_count", 0) or 0
            size = format_size(s.get("total_size", 0) or 0)
            dept_table.add_row(dept_name, str(count), size)

        console.print(dept_table)


# ─── add-department ─────────────────────────────────────────────
@cli.command("add-department")
@click.argument("name")
def add_department_cmd(name):
    """Create a new department."""
    ensure_directories()
    init_db()

    success = db_add_department(name)
    if success:
        console.print(f"[bold green]✅ Department '{name}' created successfully.[/bold green]")
    else:
        console.print(f"[bold yellow]⚠️  Department '{name}' already exists.[/bold yellow]")


# ─── list-departments ───────────────────────────────────────────
@cli.command("list-departments")
def list_departments():
    """List all departments with file counts."""
    ensure_directories()
    init_db()

    depts = get_all_departments()
    dept_stats = get_department_stats()
    stats_lookup = {s["department"]: s for s in dept_stats}

    if not depts:
        console.print("[yellow]No departments found.[/yellow]")
        return

    table = Table(title="📂 Departments")
    table.add_column("#", style="dim", justify="right")
    table.add_column("Department", style="cyan")
    table.add_column("Files", justify="right", style="green")

    for i, dept_name in enumerate(depts, 1):
        s = stats_lookup.get(dept_name.lower(), {})
        count = s.get("file_count", 0) or 0
        table.add_row(str(i), dept_name, str(count))

    console.print(table)


# ─── list-files ─────────────────────────────────────────────────
@cli.command("list-files")
@click.option("--department", required=True, help="Department name")
@click.option("--limit", default=50, help="Max files to show")
def list_files(department, limit):
    """List files in a department."""
    ensure_directories()
    init_db()

    files = get_documents_by_department(department.lower(), limit=limit)
    if not files:
        console.print(f"[yellow]No files found in department '{department}'.[/yellow]")
        return

    table = Table(title=f"📄 Files in '{department}' ({len(files)} shown)")
    table.add_column("ID", style="cyan", justify="right")
    table.add_column("Title", style="magenta", max_width=35)
    table.add_column("Category", style="green")
    table.add_column("Type", style="yellow")
    table.add_column("Size", justify="right")
    table.add_column("Date", style="dim")

    for f in files:
        title = f.get("title", "Untitled")
        if len(title) > 35:
            title = title[:32] + "..."
        table.add_row(
            str(f["id"]),
            title,
            f.get("category", "Other"),
            f.get("filetype", "?"),
            format_size(f.get("filesize", 0)),
            str(f.get("created_at", ""))[:10],
        )

    console.print(table)


# ─── reindex ────────────────────────────────────────────────────
@cli.command()
@click.option("--department", default=None, help="Reindex only this department (optional)")
def reindex(department):
    """Rebuild search index and embeddings for all or one department."""
    ensure_directories()
    init_db()

    if department:
        files = get_all_documents_in_department(department.lower())
    else:
        depts = get_all_departments()
        files = []
        for d in depts:
            files.extend(get_all_documents_in_department(d.lower()))

    if not files:
        console.print("[yellow]No files to reindex.[/yellow]")
        return

    emb = get_embedder()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
    ) as progress:
        task = progress.add_task(f"[cyan]Reindexing {len(files)} files...", total=len(files))

        for f in files:
            try:
                abs_path = get_file_path(f["filepath"])
                if not abs_path.exists():
                    progress.console.print(f"  [red]⚠ Missing file:[/red] {f['filepath']}")
                    progress.advance(task)
                    continue

                # Re-extract text
                ext = os.path.splitext(f["filename"])[1].lower()
                text = extract_text(abs_path, ext)

                # Re-generate tags
                tags = generate_tags(text)

                # Re-generate embedding
                embedding = emb.generate_embedding(text)
                emb.add_embedding(f["department"], f["id"], embedding)

                # Update database
                update_document_tags_and_embedding(f["id"], tags, f["id"])

            except Exception as e:
                progress.console.print(f"  [red]✗ Failed doc {f['id']}:[/red] {e}")

            progress.advance(task)

    console.print("[bold green]✅ Reindexing complete![/bold green]")


# ─── delete-file ────────────────────────────────────────────────
@cli.command("delete-file")
@click.option("--id", "file_id", required=True, type=int, help="File ID to delete")
@click.option("--department", required=True, help="Department the file belongs to")
def delete_file_cmd(file_id, department):
    """Delete a file permanently."""
    ensure_directories()
    init_db()

    doc = get_document_by_id(file_id, department.lower())
    if not doc:
        console.print(f"[bold red]✗ File ID {file_id} not found in department '{department}'.[/bold red]")
        return

    console.print(f"  Title:      {doc['title']}")
    console.print(f"  File:       {doc['filename']}")
    console.print(f"  Department: {doc['department']}")
    console.print(f"  Category:   {doc.get('category', 'Other')}")

    if Confirm.ask(f"\n⚠️  Delete '{doc['title']}' permanently?"):
        delete_file(doc["filepath"])
        deleted = delete_document(file_id, department.lower())
        if deleted:
            console.print(f"[bold green]✅ File {file_id} deleted successfully.[/bold green]")
        else:
            console.print(f"[bold red]✗ Failed to delete from database.[/bold red]")
    else:
        console.print("[dim]Cancelled.[/dim]")


# ─── upload ─────────────────────────────────────────────────────
@cli.command()
@click.option("--file", "filepath", required=True, type=click.Path(exists=True), help="Path to file")
@click.option("--department", required=True, help="Target department")
@click.option("--title", required=True, help="Document title")
@click.option("--category", default="Other", help="Document category")
@click.option("--notes", default="", help="Optional notes")
def upload(filepath, department, title, category, notes):
    """Upload a file via CLI with full processing pipeline."""
    ensure_directories()
    init_db()

    ext = os.path.splitext(filepath)[1].lower()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
    ) as progress:
        task = progress.add_task("[cyan]Processing upload...", total=None)

        try:
            # Read file bytes
            with open(filepath, "rb") as f:
                file_data = f.read()

            # Save via storage service
            progress.update(task, description="[cyan]💾 Saving file...")
            rel_path, filesize = save_file(file_data, department.lower(), os.path.basename(filepath))

            # Extract text
            progress.update(task, description="[cyan]📖 Extracting text...")
            abs_path = get_file_path(rel_path)
            extracted_text = extract_text(abs_path, ext)

            # Generate tags
            progress.update(task, description="[cyan]🏷️  Generating tags...")
            auto_tags = generate_tags(extracted_text)

            # Insert into database
            progress.update(task, description="[cyan]🗄️  Saving to database...")
            doc_id = insert_document(
                title=title,
                filename=os.path.basename(filepath),
                filepath=rel_path,
                filetype=ext.lstrip("."),
                filesize=filesize,
                department=department.lower(),
                category=category,
                notes=notes,
                auto_tags=auto_tags,
                extracted_text=extracted_text,
                uploaded_by="cli-admin",
            )

            # Generate embedding
            progress.update(task, description="[cyan]🧠 Creating embedding...")
            emb = get_embedder()
            embedding = emb.generate_embedding(extracted_text)
            emb.add_embedding(department.lower(), doc_id, embedding)
            update_document_tags_and_embedding(doc_id, auto_tags, doc_id)

        except Exception as e:
            console.print(f"[bold red]✗ Upload failed:[/bold red] {e}")
            return

    console.print(Panel(
        f"[bold green]✅ File uploaded successfully![/bold green]\n\n"
        f"  ID:         {doc_id}\n"
        f"  Title:      {title}\n"
        f"  Department: {department}\n"
        f"  Category:   {category}\n"
        f"  Size:       {format_size(filesize)}\n"
        f"  Auto-Tags:  {', '.join(auto_tags[:5])}{'...' if len(auto_tags) > 5 else ''}",
        title="Upload Complete"
    ))


# ─── search ─────────────────────────────────────────────────────
@cli.command()
@click.option("--department", required=True, help="Department to search in")
@click.option("--query", required=True, help="Search terms")
@click.option("--limit", default=10, help="Max results")
def search(department, query, limit):
    """Search files from CLI using keyword search."""
    ensure_directories()
    init_db()

    results = search_fts(query, department.lower(), limit=limit)

    if not results:
        console.print(f"[yellow]No results found for '{query}' in '{department}'.[/yellow]")
        return

    table = Table(title=f"🔍 Search Results for '{query}' in '{department}'")
    table.add_column("ID", style="cyan", justify="right")
    table.add_column("Title", style="magenta", max_width=30)
    table.add_column("Category", style="green")
    table.add_column("Tags", style="dim", max_width=40)
    table.add_column("Relevance", justify="right", style="yellow")

    for r in results:
        tags = parse_tags(r.get("auto_tags", "[]"))
        tag_str = ", ".join(tags[:3]) + ("..." if len(tags) > 3 else "")
        title = r.get("title", "Untitled")
        if len(title) > 30:
            title = title[:27] + "..."
        table.add_row(
            str(r["id"]),
            title,
            r.get("category", "Other"),
            tag_str,
            str(round(abs(r.get("rank", 0)), 4)),
        )

    console.print(table)
    console.print(f"[dim]Found {len(results)} result(s).[/dim]")


# ─── Entry Point ────────────────────────────────────────────────
if __name__ == "__main__":
    cli()
