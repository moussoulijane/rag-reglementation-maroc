"""Extend the frozen local index without re-encoding its law passages."""

from pathlib import Path
from uuid import uuid4

import numpy as np
from rank_bm25 import BM25Okapi

from rag_reglementation_maroc.chunking import build_chunks
from rag_reglementation_maroc.retrieval import LocalRetriever
from rag_reglementation_maroc.text import tokens

from .corpus import canonical, sha


class DomainRetriever(LocalRetriever):
    def __init__(self, base, additional, cache_dir: Path):
        articles = list(base.articles.values()) + additional
        encoder = getattr(base, "encoder", None)
        if encoder is None or not hasattr(base, "vectors") or base.vectors is None:
            super().__init__(articles, encoder, cache_dir)
            return
        self.articles = {article.id: article for article in articles}
        self.encoder = encoder
        original = (
            list(base.chunks.values()) if isinstance(base.chunks, dict) else list(base.chunks)
        )
        extra = build_chunks(additional, encoder) if additional else []
        self.chunks = original + extra
        self._bm25 = BM25Okapi([tokens(chunk.text) or ["__empty__"] for chunk in self.chunks])
        key = sha(
            canonical({"encoder": encoder.metadata, "chunks": [c.model_dump() for c in extra]})
        )
        cache_dir.mkdir(parents=True, exist_ok=True)
        target = cache_dir / f"domain-{key}.npz"
        if target.exists():
            with np.load(target, allow_pickle=False) as stored:
                vectors = stored["vectors"]
        else:
            vectors = (
                np.asarray(
                    encoder.encode_documents([chunk.text for chunk in extra]), dtype=np.float32
                )
                if extra
                else np.empty((0, base.vectors.shape[1]), dtype=np.float32)
            )
            temporary = cache_dir / f".{uuid4().hex}.tmp"
            try:
                with temporary.open("wb") as stream:
                    np.savez_compressed(stream, vectors=vectors)
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)
        if vectors.shape != (len(extra), base.vectors.shape[1]) or not np.isfinite(vectors).all():
            raise ValueError("Index métier incompatible.")
        if len(extra):
            norms = np.linalg.norm(vectors, axis=1, keepdims=True)
            if np.any(norms <= 0):
                raise ValueError("Vecteur métier nul.")
            vectors = vectors / norms
        self.vectors = np.concatenate([base.vectors, vectors], axis=0)
        self.metadata = {
            **base.metadata,
            "article_count": len(articles),
            "chunk_count": len(self.chunks),
            "index_fingerprint": sha(canonical({"base": base.metadata, "domain": key})),
            "frozen_vectors_reused": len(original),
            "new_passages_encoded": len(extra),
            "strategy": "candidate-ranking-plus-reviewed-reference-expansion",
        }
