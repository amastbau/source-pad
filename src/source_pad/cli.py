"""CLI: source-pad index/query/serve/stats/clear."""

import argparse
import sys

from rich.console import Console

console = Console()


def cmd_index_github(args):
    from .config import Config
    from .rag import RAG
    from .indexer import index_github

    # Parse owner/repo
    parts = args.repo.split("/")
    if len(parts) != 2:
        console.print("[red]Use format: owner/repo (e.g. amastbau/hybrid-llm)[/red]")
        sys.exit(1)

    rag = RAG(Config.from_env())
    index_github(rag, owner=parts[0], repo=parts[1], branch=args.branch)


def cmd_index_dir(args):
    from .config import Config
    from .rag import RAG
    from .indexer import index_directory

    rag = RAG(Config.from_env())
    index_directory(rag, args.path)


def cmd_index_url(args):
    from .config import Config
    from .rag import RAG
    from .crawler import crawl

    rag = RAG(Config.from_env())
    crawl(rag, args.url, max_depth=args.depth, max_pages=args.max_pages)


def cmd_query(args):
    from .config import Config
    from .rag import RAG

    rag = RAG(Config.from_env())
    result = rag.query(args.question)
    console.print(f"\n[bold]{result['response']}[/bold]\n")
    if result["sources"]:
        console.print("[dim]Sources:[/dim]")
        for s in result["sources"]:
            url = s.get("url", s.get("metadata", {}).get("file_path", "?"))
            console.print(f"  [dim]- {url} (score: {s['score']:.3f})[/dim]")


def cmd_serve(args):
    import uvicorn
    from .config import Config

    config = Config.from_env()
    host = args.host or config.host
    port = args.port or config.port

    console.print(f"[bold]Starting source-pad at http://{host}:{port}[/bold]")
    uvicorn.run("source_pad.web:app", host=host, port=port, reload=args.reload)


def cmd_stats(args):
    from .config import Config
    from .rag import RAG

    rag = RAG(Config.from_env())
    stats = rag.stats()
    console.print(f"Collection: {stats['collection']}")
    console.print(f"Documents:  {stats['documents']}")
    console.print(f"LLM:        {stats['llm']}")
    console.print(f"Embeddings: {stats['embeddings']}")


def cmd_clear(args):
    from .config import Config
    from .rag import RAG

    rag = RAG(Config.from_env())
    rag.clear()


def main():
    parser = argparse.ArgumentParser(
        prog="source-pad",
        description="Index your code, ask questions. Works with local LLMs.",
    )
    sub = parser.add_subparsers(dest="command")

    # index github
    idx = sub.add_parser("index", help="Index sources")
    idx_sub = idx.add_subparsers(dest="source")

    gh = idx_sub.add_parser("github", help="Index a GitHub repo")
    gh.add_argument("repo", help="owner/repo (e.g. amastbau/hybrid-llm)")
    gh.add_argument("--branch", default="main")
    gh.set_defaults(func=cmd_index_github)

    dr = idx_sub.add_parser("dir", help="Index a local directory")
    dr.add_argument("path", help="Path to directory")
    dr.set_defaults(func=cmd_index_dir)

    ur = idx_sub.add_parser("url", help="Crawl and index a URL")
    ur.add_argument("url", help="URL to crawl")
    ur.add_argument("--depth", type=int, default=2, help="Max link depth (default: 2)")
    ur.add_argument("--max-pages", type=int, default=50, help="Max pages (default: 50)")
    ur.set_defaults(func=cmd_index_url)

    # query
    q = sub.add_parser("query", help="Ask a question")
    q.add_argument("question")
    q.set_defaults(func=cmd_query)

    # serve
    s = sub.add_parser("serve", help="Start web UI")
    s.add_argument("--host", default=None)
    s.add_argument("--port", type=int, default=None)
    s.add_argument("--reload", action="store_true")
    s.set_defaults(func=cmd_serve)

    # stats
    st = sub.add_parser("stats", help="Show index stats")
    st.set_defaults(func=cmd_stats)

    # clear
    cl = sub.add_parser("clear", help="Clear all indexed documents")
    cl.set_defaults(func=cmd_clear)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()
