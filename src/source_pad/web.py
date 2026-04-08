"""Web UI: FastAPI server with streaming chat."""

import asyncio
import json
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import Config
from .rag import RAG
from .indexer import index_github, index_directory
from .crawler import crawl

app = FastAPI(title="source-pad", version="0.1.0")

# State
_config: Config | None = None
_rag: RAG | None = None
_history: list[dict] = []

SYSTEM_PROMPT = """You are a helpful assistant that answers questions based on the provided context.
If the context contains relevant information, use it to answer accurately and cite sources.
If no relevant context is found, say so honestly and answer from general knowledge."""

STATIC_DIR = Path(__file__).parent.parent.parent / "static"


def get_rag() -> RAG:
    global _config, _rag
    if _rag is None:
        _config = Config.from_env()
        _rag = RAG(_config)
    return _rag


# --- Models ---

class ChatMessage(BaseModel):
    message: str


class IndexGithubRequest(BaseModel):
    repo: str  # "owner/repo"
    branch: str = "main"


class IndexDirRequest(BaseModel):
    path: str


class CrawlRequest(BaseModel):
    url: str
    max_depth: int = 2
    max_pages: int = 50


# --- Routes ---

@app.get("/", response_class=HTMLResponse)
async def index():
    html_file = STATIC_DIR / "index.html"
    if html_file.exists():
        return HTMLResponse(html_file.read_text())
    return HTMLResponse("<h1>source-pad</h1><p>static/index.html not found</p>")


@app.get("/api/health")
async def health():
    rag = get_rag()
    return {"status": "ok", "documents": rag.doc_count()}


@app.get("/api/stats")
async def stats():
    return get_rag().stats()


@app.post("/api/chat/stream")
async def chat_stream(msg: ChatMessage):
    rag = get_rag()
    message = msg.message  # capture before passing to sync generator

    def generate():
        global _history

        def debug(step, data):
            return f"data: {json.dumps({'type': 'debug', 'step': step, 'data': data})}\n\n"

        # System info
        yield debug("system_info", {
            "llm": f"{rag.config.llm_provider}/{rag.config.llm_model}",
            "embeddings": f"ollama/{rag.config.embedding_model}",
            "documents": rag.doc_count(),
        })

        # Query
        yield debug("query", {"query": message})

        # Get RAG context
        context = ""
        try:
            yield debug("rag_start", {"status": "Searching vector store..."})
            context = rag.get_context(message, max_results=5)
            if context:
                results = rag.search(message, top_k=5)
                sources = [
                    {
                        "url": r["metadata"].get("url", r.get("doc_id", "?")),
                        "score": r["score"],
                        "doc_id": r["doc_id"],
                    }
                    for r in results
                ]
                yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"
                yield debug("rag_results", {
                    "matches": len(results),
                    "context_length": len(context),
                    "top_sources": [
                        f"{r['doc_id']} ({r['score']:.3f})" for r in results[:5]
                    ],
                })
            else:
                yield debug("rag_results", {"matches": 0, "context_length": 0})
        except Exception as e:
            yield f"data: {json.dumps({'type': 'rag_error', 'error': str(e)})}\n\n"
            yield debug("rag_error", {"error": str(e)})

        # Build messages
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if context:
            messages[0]["content"] += f"\n\n{context}"
        for h in _history[-10:]:
            messages.append(h)
        messages.append({"role": "user", "content": message})

        yield debug("llm_prompt", {
            "message_count": len(messages),
            "total_chars": sum(len(m["content"]) for m in messages),
            "messages": [
                {"role": m["role"], "content_length": len(m["content"]),
                 "preview": m["content"][:200] + ("..." if len(m["content"]) > 200 else "")}
                for m in messages
            ],
        })

        # Stream from LLM
        try:
            from llama_index.core.llms import ChatMessage as LIChatMessage
            from llama_index.core import Settings
            import time

            rag._get_index()  # ensures settings are configured

            li_messages = [
                LIChatMessage(role=m["role"], content=m["content"]) for m in messages
            ]

            yield debug("llm_start", {"status": "Generating response..."})
            t0 = time.time()

            full_response = ""
            token_count = 0
            response = Settings.llm.stream_chat(li_messages)
            for chunk in response:
                if chunk and hasattr(chunk, "delta") and chunk.delta:
                    full_response += chunk.delta
                    token_count += 1
                    yield f"data: {json.dumps({'type': 'content', 'content': chunk.delta})}\n\n"

            elapsed = time.time() - t0
            _history.append({"role": "user", "content": message})
            _history.append({"role": "assistant", "content": full_response})

            yield debug("llm_done", {
                "response_length": len(full_response),
                "chunks": token_count,
                "elapsed_s": round(elapsed, 2),
            })
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e), 'error_type': type(e).__name__})}\n\n"
            yield debug("llm_error", {"error": str(e), "type": type(e).__name__})

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/api/index/github")
async def api_index_github(req: IndexGithubRequest):
    rag = get_rag()
    parts = req.repo.split("/")
    if len(parts) != 2:
        return {"error": "Use format: owner/repo"}
    count = index_github(rag, owner=parts[0], repo=parts[1], branch=req.branch)
    return {"indexed": count, "repo": req.repo}


@app.post("/api/index/directory")
async def api_index_dir(req: IndexDirRequest):
    rag = get_rag()
    count = index_directory(rag, req.path)
    return {"indexed": count, "path": req.path}


@app.post("/api/index/crawl")
async def api_crawl(req: CrawlRequest):
    rag = get_rag()
    count = crawl(rag, req.url, max_depth=req.max_depth, max_pages=req.max_pages)
    return {"indexed": count, "url": req.url}


@app.post("/api/clear")
async def api_clear():
    global _history
    get_rag().clear()
    _history = []
    return {"status": "cleared"}


# Mount static files (CSS, JS)
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
