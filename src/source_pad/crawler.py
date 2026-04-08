"""Crawl web pages and index their content."""

import re
from urllib.parse import urlparse, urljoin
from typing import Optional

import httpx
from rich.console import Console

from .rag import RAG

console = Console()

# Extract links from HTML
LINK_PATTERN = re.compile(r'href=["\']([^"\']+)["\']')


def _extract_text(html: str) -> tuple[str, str]:
    """Extract title and text from HTML."""
    # Title
    title = ""
    title_match = re.search(r"<title>([^<]+)</title>", html, re.IGNORECASE)
    if title_match:
        title = title_match.group(1).strip()

    # Remove script/style blocks
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    # Strip tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return title, text


def _extract_links(html: str, base_url: str) -> list[str]:
    """Extract absolute URLs from HTML."""
    links = []
    for match in LINK_PATTERN.finditer(html):
        href = match.group(1)
        if href.startswith("#") or href.startswith("mailto:") or href.startswith("javascript:"):
            continue
        url = urljoin(base_url, href)
        # Only follow http(s)
        if url.startswith("http"):
            links.append(url.split("#")[0])  # strip fragment
    return list(set(links))


def _same_domain(url1: str, url2: str) -> bool:
    return urlparse(url1).netloc == urlparse(url2).netloc


def crawl(
    rag: RAG,
    url: str,
    max_depth: int = 2,
    max_pages: int = 50,
    same_domain: bool = True,
) -> int:
    """Crawl a URL and follow links up to max_depth.

    Args:
        rag: RAG instance to index into
        url: Starting URL
        max_depth: How many link hops to follow (0 = just this page)
        max_pages: Maximum pages to crawl
        same_domain: Only follow links on the same domain

    Returns:
        Number of pages indexed
    """
    visited: set[str] = set()
    queue: list[tuple[str, int]] = [(url, 0)]
    docs: list[dict] = []

    console.print(f"[dim]Crawling {url} (depth={max_depth}, max={max_pages})...[/dim]")

    with httpx.Client(timeout=30, follow_redirects=True, verify=False) as client:
        while queue and len(docs) < max_pages:
            current_url, depth = queue.pop(0)

            # Normalize
            current_url = current_url.rstrip("/")
            if current_url in visited:
                continue
            visited.add(current_url)

            # Fetch
            try:
                resp = client.get(current_url)
                if resp.status_code != 200:
                    continue
                content_type = resp.headers.get("content-type", "")
                if "text/html" not in content_type:
                    continue
            except Exception as e:
                console.print(f"  [dim red]Failed: {current_url}: {e}[/dim red]")
                continue

            html = resp.text
            title, text = _extract_text(html)

            if not text or len(text) < 50:
                continue

            title = title or current_url
            console.print(f"  [dim][{len(docs)+1}] depth={depth} {title[:60]}[/dim]")

            docs.append({
                "content": f"# {title}\n\n{text}",
                "id": f"web:{current_url}",
                "metadata": {
                    "source": "web",
                    "url": current_url,
                    "title": title,
                    "depth": depth,
                },
            })

            # Follow links
            if depth < max_depth:
                for link in _extract_links(html, current_url):
                    if link not in visited:
                        if same_domain and not _same_domain(url, link):
                            continue
                        queue.append((link, depth + 1))

    if docs:
        count = rag.ingest(docs)
        console.print(f"[green]Crawled and indexed {count} pages from {url}[/green]")
        return count

    console.print("[yellow]No pages crawled[/yellow]")
    return 0
