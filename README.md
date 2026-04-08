# source-pad

Index your code, ask questions. Works with local LLMs — no cloud, no API keys.

Built on [LlamaIndex](https://www.llamaindex.ai/) + [ChromaDB](https://www.trychroma.com/). Pairs with [hybrid-llm](https://github.com/amastbau/hybrid-llm) for running LLMs on your phone or PC.

## Quick start

### Option A: Container (easiest)

```bash
# 1. Start Ollama (needed for embeddings + chat)
ollama pull nomic-embed-text
ollama pull llama3.1:8b

# 2. Run source-pad
podman run -d --name source-pad \
  --network host \
  -v source-pad-data:/app/data \
  quay.io/amastbau/source-pad:latest

# 3. Open http://localhost:8090
```

That's it. The image comes with the source-pad project itself already indexed — you can start asking questions immediately. Use `docker` instead of `podman` if you prefer.

To use the phone LLM instead of Ollama for chat:
```bash
podman run -d --name source-pad \
  --network host \
  -v source-pad-data:/app/data \
  -e LLM_PROVIDER=local \
  -e LOCAL_LLM_URL=http://localhost:8080 \
  -e LLM_MODEL=gemma-2-2b-it-q4_k_m.gguf \
  quay.io/amastbau/source-pad:latest
```

### Option B: From source

```bash
# 1. Start Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama pull nomic-embed-text   # required for indexing (always)
ollama pull llama3.1:8b        # optional — only if using Ollama as your chat LLM

# 2. Install source-pad
git clone https://github.com/amastbau/source-pad.git
cd source-pad
uv sync
cp .env.example .env
# Edit .env if using phone LLM (see below)

# 3. Run
source-pad serve
# Open http://localhost:8090
```

See the [hybrid-llm Getting Started guide](https://github.com/amastbau/hybrid-llm/blob/main/GETTING_STARTED.md) for all LLM options (PC, phone, model selection, Llama Stack).

**Ollama is always required** for embeddings, even when using the phone LLM for chat.

### Index some code

```bash
# Via the web UI: click "+ Index" and pick GitHub / directory / URL

# Or via CLI (from source install):
source-pad index dir .
source-pad index github amastbau/hybrid-llm
source-pad index url https://docs.example.com --depth 2
```

### Ask questions

```bash
# Web UI at http://localhost:8090

# Or via CLI:
source-pad query "How does deploy_llm.py deploy a model to the phone?"
source-pad query "What is the architecture of source-pad?"
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
| `PORT` | `8090` | Web UI port |

## CLI commands

```
source-pad index github <owner/repo>   Index a GitHub repo
source-pad index dir <path>            Index a local directory
source-pad index url <url>             Crawl and index a URL
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
