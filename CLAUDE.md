# source-pad

Simple RAG chatbot for code. Works with local LLMs (Ollama or OpenAI-compatible).

## Stack

- Python 3.12+, FastAPI, LlamaIndex, ChromaDB
- Build: uv (pyproject.toml, hatchling)
- Package: src/source_pad/

## Commands

```bash
uv sync                                # install
source-pad serve                       # web UI at :8080
source-pad index dir <path>            # index local files
source-pad index github <owner/repo>   # index GitHub repo
source-pad query "question"            # CLI query
source-pad stats                       # show index stats
source-pad clear                       # clear index
```

## Key files

- `src/source_pad/config.py`   — Config from env vars (1 flat dataclass)
- `src/source_pad/rag.py`      — LlamaIndex RAG with ChromaDB
- `src/source_pad/indexer.py`   — GitHub + local file indexing
- `src/source_pad/crawler.py`   — Web crawler (follows links to configurable depth)
- `src/source_pad/web.py`       — FastAPI server (7 endpoints)
- `src/source_pad/cli.py`       — CLI entry point
- `static/`                     — Frontend (HTML/CSS/JS)

## Architecture

```
Config (.env) -> CLI/Web -> Indexer -> RAG (LlamaIndex + ChromaDB)
                         -> RAG -> LLM (Ollama or OpenAI-compatible)
```

Embeddings always use Ollama, even when LLM runs on phone.
