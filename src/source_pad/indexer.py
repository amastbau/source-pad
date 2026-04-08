"""Index GitHub repos and local directories into the RAG store."""

import os
from pathlib import Path

from rich.console import Console

from .rag import RAG

console = Console()

# File extensions worth indexing
CODE_EXTENSIONS = {
    ".md", ".rst", ".txt", ".py", ".yaml", ".yml", ".json",
    ".toml", ".cfg", ".ini", ".sh", ".bash",
    ".js", ".ts", ".jsx", ".tsx", ".html", ".css",
    ".go", ".rs", ".java", ".c", ".cpp", ".h",
    ".rb", ".php", ".swift", ".kt",
    ".dockerfile", ".containerfile",
}

# Directories to skip
SKIP_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    ".tox", ".mypy_cache", ".pytest_cache", "dist", "build",
    ".egg-info", "data", ".cache",
}


def index_github(
    rag: RAG,
    owner: str,
    repo: str,
    branch: str = "main",
    token: str | None = None,
) -> int:
    """Index a GitHub repository."""
    try:
        from llama_index.readers.github import GithubRepositoryReader, GithubClient
    except ImportError:
        console.print("[red]llama-index-readers-github not installed[/red]")
        return 0

    token = token or os.environ.get("GITHUB_TOKEN")
    if not token:
        console.print("[red]GITHUB_TOKEN not set[/red]")
        return 0

    console.print(f"[dim]Loading {owner}/{repo} from GitHub...[/dim]")

    github_client = GithubClient(github_token=token)
    reader = GithubRepositoryReader(
        github_client=github_client,
        owner=owner,
        repo=repo,
        filter_file_extensions=(
            list(CODE_EXTENSIONS),
            GithubRepositoryReader.FilterType.INCLUDE,
        ),
    )

    documents = reader.load_data(branch=branch)

    docs = []
    for doc in documents:
        file_path = doc.metadata.get("file_path", "unknown")
        docs.append(
            {
                "content": doc.text,
                "id": f"github:{owner}/{repo}:{file_path}",
                "metadata": {
                    **doc.metadata,
                    "source": "github",
                    "repo": f"{owner}/{repo}",
                    "url": f"https://github.com/{owner}/{repo}/blob/{branch}/{file_path}",
                },
            }
        )

    count = rag.ingest(docs)
    console.print(f"[green]Indexed {count} files from {owner}/{repo}[/green]")
    return count


def index_directory(rag: RAG, path: str) -> int:
    """Index a local directory."""
    root = Path(path).resolve()
    if not root.is_dir():
        console.print(f"[red]Not a directory: {root}[/red]")
        return 0

    console.print(f"[dim]Scanning {root}...[/dim]")

    docs = []
    for file_path in root.rglob("*"):
        # Skip directories
        if file_path.is_dir():
            continue
        # Skip hidden/excluded dirs
        if any(part in SKIP_DIRS for part in file_path.parts):
            continue
        # Check extension
        if file_path.suffix.lower() not in CODE_EXTENSIONS:
            # Also index files with no extension if they look like config (Makefile, Dockerfile, etc.)
            if file_path.suffix:
                continue

        try:
            content = file_path.read_text(errors="ignore")
        except Exception:
            continue

        if not content.strip():
            continue

        rel = file_path.relative_to(root)
        docs.append(
            {
                "content": content,
                "id": f"local:{rel}",
                "metadata": {
                    "source": "local",
                    "file_path": str(rel),
                    "directory": str(root),
                },
            }
        )

    count = rag.ingest(docs)
    console.print(f"[green]Indexed {count} files from {root}[/green]")
    return count
