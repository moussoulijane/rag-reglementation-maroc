"""Configuration explicite ; aucun téléchargement implicite au démarrage."""

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from .answering import AbstentionPolicy, AnswerService, OllamaClient
from .chunking import build_chunks
from .ingestion import load_articles
from .retrieval import LocalRetriever


@dataclass(frozen=True)
class Settings:
    data_dir: Path = Path("data")
    encoder: str = "none"
    preprocessing: str = "normalized"
    backend: str = "local"
    generator: str = "extractive"
    policy_path: Path = Path("evaluation/abstention_policy.json")
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:7b"

    @classmethod
    def from_env(cls):
        return cls(
            data_dir=Path(os.getenv("RAG_DATA_DIR", "data")),
            encoder=os.getenv("RAG_ENCODER", "none"),
            preprocessing=os.getenv("RAG_PREPROCESSING", "normalized"),
            backend=os.getenv("RAG_BACKEND", "local"),
            generator=os.getenv("RAG_GENERATOR", "extractive"),
            policy_path=Path(os.getenv("RAG_POLICY_PATH", "evaluation/abstention_policy.json")),
            ollama_url=os.getenv("RAG_OLLAMA_URL", "http://127.0.0.1:11434"),
            ollama_model=os.getenv("RAG_OLLAMA_MODEL", "qwen2.5:7b"),
        )


def build_retriever(settings: Settings):
    articles = load_articles(settings.data_dir / "processed" / "articles.jsonl")
    encoder = None
    if settings.encoder == "multilingual":
        from .embeddings import MultilingualEncoder

        encoder = MultilingualEncoder(
            settings.data_dir / "models", allow_download=False, preprocessing=settings.preprocessing
        )
    elif settings.encoder != "none":
        raise ValueError("RAG_ENCODER doit valoir none ou multilingual.")
    if settings.backend == "local":
        return LocalRetriever(articles, encoder, settings.data_dir / "index")
    if settings.backend == "opensearch":
        from .opensearch_backend import OpenSearchRetriever

        return OpenSearchRetriever(articles, build_chunks(articles, encoder), encoder=encoder)
    raise ValueError("RAG_BACKEND doit valoir local ou opensearch.")


def build_service(settings: Settings, retriever=None) -> AnswerService:
    selected = retriever if retriever is not None else build_retriever(settings)
    if hasattr(selected, "check_ready"):
        selected.check_ready()
    policy = AbstentionPolicy()
    status = "illustrative_defaults"
    if settings.policy_path.exists():
        data = json.loads(settings.policy_path.read_text(encoding="utf-8"))
        actual_signature = hashlib.sha256(
            json.dumps(selected.metadata, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        if data.get("retriever_signature") == actual_signature:
            policy = AbstentionPolicy.load(settings.policy_path)
            status = "development_calibrated"
        else:
            status = "uncalibrated_for_this_index"
    service = AnswerService(
        selected,
        policy,
        OllamaClient(settings.ollama_url, settings.ollama_model),
    )
    service.policy_status = status
    return service
