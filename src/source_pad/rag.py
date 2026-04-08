"""LlamaIndex RAG with ChromaDB. Supports Ollama and local (OpenAI-compatible) LLMs."""

import os
from typing import Optional

import chromadb
from llama_index.core import Document, VectorStoreIndex, StorageContext, Settings
from llama_index.core.node_parser import SentenceSplitter
from llama_index.vector_stores.chroma import ChromaVectorStore
from rich.console import Console

from .config import Config

console = Console()


def _create_llm(config: Config):
    """Create LLM based on provider."""
    if config.llm_provider == "local":
        from llama_index.llms.openai_like import OpenAILike

        return OpenAILike(
            model=config.llm_model,
            api_key="not-needed",
            api_base=f"{config.local_llm_url}/v1",
            is_chat_model=True,
            timeout=300.0,
        )
    else:  # ollama
        from llama_index.llms.ollama import Ollama

        return Ollama(
            model=config.llm_model,
            base_url=config.ollama_url,
            request_timeout=120.0,
        )


def _create_embed_model(config: Config):
    """Create embedding model (always Ollama)."""
    from llama_index.embeddings.ollama import OllamaEmbedding

    return OllamaEmbedding(
        model_name=config.embedding_model,
        base_url=config.ollama_url,
    )


class RAG:
    """Simple RAG: index documents, search, query."""

    def __init__(self, config: Config | None = None, collection: str = "source-pad"):
        self.config = config or Config.from_env()
        self.collection_name = collection
        self._index: Optional[VectorStoreIndex] = None
        self._chroma_client = None
        self._collection = None

        # Configure LlamaIndex
        Settings.llm = _create_llm(self.config)
        Settings.embed_model = _create_embed_model(self.config)
        Settings.node_parser = SentenceSplitter(chunk_size=512, chunk_overlap=50)

        console.print(f"[dim]LLM: {self.config.llm_provider}/{self.config.llm_model}[/dim]")
        console.print(f"[dim]Embeddings: ollama/{self.config.embedding_model}[/dim]")

    def _get_chroma(self):
        if self._chroma_client is None:
            if self.config.chroma_path:
                os.makedirs(self.config.chroma_path, exist_ok=True)
                self._chroma_client = chromadb.PersistentClient(
                    path=self.config.chroma_path
                )
                console.print(f"[dim]ChromaDB: {self.config.chroma_path}[/dim]")
            else:
                self._chroma_client = chromadb.Client()
                console.print("[dim]ChromaDB: in-memory[/dim]")
        return self._chroma_client

    def _get_collection(self):
        if self._collection is None:
            client = self._get_chroma()
            self._collection = client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    def _get_index(self) -> VectorStoreIndex:
        if self._index is None:
            collection = self._get_collection()
            vector_store = ChromaVectorStore(chroma_collection=collection)
            storage_context = StorageContext.from_defaults(vector_store=vector_store)

            if collection.count() > 0:
                self._index = VectorStoreIndex.from_vector_store(
                    vector_store, storage_context=storage_context
                )
            else:
                self._index = VectorStoreIndex(
                    [], storage_context=storage_context
                )
        return self._index

    def ingest(self, documents: list[dict]) -> int:
        """Ingest documents. Each dict has 'content', 'id', 'metadata'."""
        if not documents:
            return 0

        llama_docs = []
        for doc in documents:
            metadata = doc.get("metadata", {})
            metadata["doc_id"] = doc.get("id", "unknown")
            llama_docs.append(
                Document(
                    text=doc["content"],
                    doc_id=doc.get("id", "unknown"),
                    metadata=metadata,
                )
            )

        index = self._get_index()
        for doc in llama_docs:
            index.insert(doc)

        console.print(f"[green]Indexed {len(llama_docs)} documents[/green]")
        return len(llama_docs)

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Search for similar documents (retrieval only, no LLM)."""
        index = self._get_index()
        retriever = index.as_retriever(similarity_top_k=top_k)
        nodes = retriever.retrieve(query)

        return [
            {
                "content": node.text,
                "score": node.score,
                "metadata": node.metadata,
                "doc_id": node.metadata.get("doc_id", "unknown"),
            }
            for node in nodes
        ]

    def get_context(self, query: str, max_results: int = 5) -> str:
        """Get formatted context string for injection into LLM prompt."""
        results = self.search(query, top_k=max_results)
        if not results:
            return ""

        urls = sorted(
            set(r["metadata"]["url"] for r in results if "url" in r["metadata"])
        )

        context = "## Sources:\n"
        for url in urls:
            context += f"  - {url}\n"
        context += "\n## Relevant content:\n"
        for i, r in enumerate(results):
            context += f"[{i + 1}] (source: {r['doc_id']}, relevance: {r['score']:.3f}):\n"
            context += f"{r['content']}\n---\n"
        return context

    def query(self, query_text: str, top_k: int = 5) -> dict:
        """Query with RAG: retrieves context and generates a response via LLM."""
        index = self._get_index()
        engine = index.as_query_engine(
            similarity_top_k=top_k, response_mode="compact"
        )
        response = engine.query(query_text)

        sources = []
        for node in response.source_nodes:
            info = {
                "content": node.text[:500],
                "score": node.score,
                "metadata": node.metadata,
            }
            if "url" in node.metadata:
                info["url"] = node.metadata["url"]
            sources.append(info)

        return {"response": str(response), "sources": sources}

    def clear(self):
        """Delete all indexed documents."""
        client = self._get_chroma()
        try:
            client.delete_collection(self.collection_name)
            console.print(f"[yellow]Cleared collection: {self.collection_name}[/yellow]")
        except Exception:
            pass
        self._index = None
        self._collection = None

    def stats(self) -> dict:
        collection = self._get_collection()
        return {
            "collection": self.collection_name,
            "documents": collection.count(),
            "llm": f"{self.config.llm_provider}/{self.config.llm_model}",
            "embeddings": f"ollama/{self.config.embedding_model}",
        }

    def doc_count(self) -> int:
        return self._get_collection().count()
