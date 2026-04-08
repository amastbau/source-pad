"""Configuration from environment variables."""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    llm_provider: str  # "ollama" or "local"
    llm_model: str
    ollama_url: str
    local_llm_url: str
    embedding_model: str
    chroma_path: str | None  # None = in-memory
    host: str
    port: int

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            llm_provider=os.environ.get("LLM_PROVIDER", "ollama"),
            llm_model=os.environ.get("LLM_MODEL", "llama3.1:8b"),
            ollama_url=os.environ.get("OLLAMA_URL", "http://localhost:11434"),
            local_llm_url=os.environ.get("LOCAL_LLM_URL", "http://localhost:8080"),
            embedding_model=os.environ.get("EMBEDDING_MODEL", "nomic-embed-text"),
            chroma_path=os.environ.get("CHROMA_PATH", "./data/chroma"),
            host=os.environ.get("HOST", "0.0.0.0"),
            port=int(os.environ.get("PORT", "8090")),
        )
