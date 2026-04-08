# source-pad

Index your code, ask questions. Works with local LLMs — no cloud, no API keys.

Built on [LlamaIndex](https://www.llamaindex.ai/) + [ChromaDB](https://www.trychroma.com/). Pairs with [hybrid-llm](https://github.com/amastbau/hybrid-llm) for running LLMs on your phone or PC.

## Quick start

### 1. Start an LLM

**Option A: Ollama on your PC** (recommended)
```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.1:8b        # chat model
ollama pull nomic-embed-text   # embedding model (required for indexing)
```

**Option B: Phone via hybrid-llm**
```bash
cd /path/to/hybrid-llm
python deploy_llm.py
# Ollama still needed on PC for embeddings:
ollama pull nomic-embed-text
```

### 2. Install source-pad

```bash
git clone https://github.com/amastbau/source-pad.git
cd source-pad
uv sync
cp .env.example .env
# Edit .env if using phone LLM (see below)
```

### 3. Index some code

```bash
# Index this project itself
source-pad index dir .

# Index a GitHub repo (needs GITHUB_TOKEN in .env)
source-pad index github amastbau/hybrid-llm
source-pad index github amastbau/source-pad
```

### 4. Ask questions

```bash
# CLI
source-pad query "How does deploy_llm.py deploy a model to the phone?"
source-pad query "What is the architecture of source-pad?"

# Web UI
source-pad serve
# Open http://localhost:8080
```

## Using with hybrid-llm

### Ollama on PC (default)

```env
LLM_PROVIDER=ollama
OLLAMA_URL=http://localhost:11434
LLM_MODEL=llama3.1:8b
EMBEDDING_MODEL=nomic-embed-text
```

### Phone LLM via USB

Deploy a model to your phone with [hybrid-llm](https://github.com/amastbau/hybrid-llm), then point source-pad at it:

```env
LLM_PROVIDER=local
LOCAL_LLM_URL=http://localhost:8080
LLM_MODEL=gemma-2-2b-it-q4_k_m.gguf

# Ollama still needed for embeddings (phone doesn't serve an embedding endpoint)
OLLAMA_URL=http://localhost:11434
EMBEDDING_MODEL=nomic-embed-text
```

The phone serves Gemma 2B via an OpenAI-compatible API at `localhost:8080` (forwarded over USB via `adb`). Chat runs on the phone, embeddings run on your PC via Ollama.

### Example: index both projects and ask questions

```bash
# Set up
export GITHUB_TOKEN=ghp_...

# Index
source-pad index github amastbau/hybrid-llm
source-pad index github amastbau/source-pad

# Ask
source-pad query "How do I deploy an LLM to my Android phone?"
source-pad query "What files does source-pad index from a GitHub repo?"
source-pad query "What embedding model does source-pad use?"

# Or use the web UI
source-pad serve
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `ollama` | `ollama` or `local` (OpenAI-compatible) |
| `LLM_MODEL` | `llama3.1:8b` | Model name |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama server URL |
| `LOCAL_LLM_URL` | `http://localhost:8080` | Local LLM endpoint (for `local` provider) |
| `EMBEDDING_MODEL` | `nomic-embed-text` | Ollama embedding model |
| `CHROMA_PATH` | `./data/chroma` | ChromaDB storage path |
| `GITHUB_TOKEN` | — | GitHub PAT for indexing repos |
| `PORT` | `8080` | Web UI port |

## CLI commands

```
source-pad index github <owner/repo>   Index a GitHub repo
source-pad index dir <path>            Index a local directory
source-pad query "question"            Ask a question (CLI)
source-pad serve                       Start the web UI
source-pad stats                       Show index stats
source-pad clear                       Clear all indexed documents
```

## How it works

```
You index code  ──>  LlamaIndex chunks + embeds  ──>  ChromaDB stores vectors
You ask a question  ──>  ChromaDB finds relevant chunks  ──>  LLM generates answer with context
```

The LLM never sees your entire codebase — only the most relevant chunks for your question (RAG). This works well even with small models like Gemma 2B.
