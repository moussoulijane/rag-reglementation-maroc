"""BM25, cosinus et RRF sur les mêmes passages et contraintes."""

import hashlib
import json
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

from .chunking import build_chunks
from .models import Article, SearchHit
from .text import requested_articles, tokens

MODES = {"bm25", "semantic", "hybrid"}


def reciprocal_rank_fusion(rankings: list[list[int]], constant: int = 60) -> dict[int, float]:
    if constant < 1:
        raise ValueError("La constante RRF doit être positive.")
    scores: dict[int, float] = {}
    for ranking in rankings:
        if len(set(ranking)) != len(ranking):
            raise ValueError("Une liste ne doit pas contenir de doublon.")
        for rank, index in enumerate(ranking, start=1):
            scores[index] = scores.get(index, 0.0) + 1.0 / (constant + rank)
    return scores


class LocalRetriever:
    def __init__(self, articles: list[Article], encoder=None, cache_dir: Path | None = None):
        if not articles or len({item.id for item in articles}) != len(articles):
            raise ValueError("Articles vides ou identifiants dupliqués.")
        self.articles = {item.id: item for item in articles}
        self.encoder = encoder
        self.chunks = build_chunks(articles, encoder)
        self._bm25 = BM25Okapi([tokens(chunk.text) or ["__empty__"] for chunk in self.chunks])
        self.vectors = None
        self.metadata = {
            "backend": "local",
            "article_count": len(articles),
            "chunk_count": len(self.chunks),
            "chunker": "model-tokenizer-110-overlap-20"
            if encoder
            else "characters-650-overlap-100",
            "rrf_constant": 60,
            "candidate_k": 50,
            "encoder": encoder.metadata if encoder else None,
        }
        if encoder is not None:
            payload = {"chunks": [c.model_dump() for c in self.chunks], "encoder": encoder.metadata}
            digest = hashlib.sha256(
                json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
            ).hexdigest()
            target = Path(cache_dir) / f"{digest}.npz" if cache_dir else None
            if target is not None and target.exists():
                with np.load(target, allow_pickle=False) as saved:
                    vectors = saved["vectors"]
            else:
                vectors = np.asarray(
                    encoder.encode_documents([chunk.text for chunk in self.chunks]),
                    dtype=np.float32,
                )
                if target is not None:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    np.savez_compressed(target, vectors=vectors)
            if vectors.ndim != 2 or vectors.shape[0] != len(self.chunks):
                raise ValueError("La matrice ne correspond pas aux passages.")
            if not np.isfinite(vectors).all():
                raise ValueError("Un embedding contient une valeur non finie.")
            norms = np.linalg.norm(vectors, axis=1, keepdims=True)
            if np.any(norms <= 0):
                raise ValueError("Un embedding nul ne définit pas de cosinus.")
            self.vectors = vectors / norms
            self.metadata["index_fingerprint"] = digest

    def search(
        self,
        question: str,
        language: str | None = None,
        mode: str = "bm25",
        top_k: int = 5,
    ) -> list[SearchHit]:
        if mode not in MODES or not 1 <= top_k <= 20:
            raise ValueError("Mode inconnu ou top_k en dehors de [1,20].")
        if language not in {None, "fr", "ar"}:
            raise ValueError("La langue de source doit être fr, ar ou absente.")
        if mode != "bm25" and self.encoder is None:
            raise ValueError("Ce mode requiert un encodeur ; aucun repli implicite.")
        explicit = requested_articles(question)
        allowed = [
            i
            for i, chunk in enumerate(self.chunks)
            if (language is None or self.articles[chunk.article_ref].language == language)
            and (not explicit or self.articles[chunk.article_ref].article_id in explicit)
        ]
        if not allowed:
            return []
        lexical = np.asarray(self._bm25.get_scores(tokens(question)))
        semantic = None
        if mode != "bm25":
            query = np.asarray(self.encoder.encode_query(question), dtype=np.float32).reshape(-1)
            if query.shape[0] != self.vectors.shape[1] or not np.isfinite(query).all():
                raise ValueError("Embedding de requête incompatible.")
            norm = np.linalg.norm(query)
            if norm <= 0:
                raise ValueError("Embedding de requête nul.")
            semantic = self.vectors @ (query / norm)
        lexical_ranking = sorted(
            [i for i in allowed if lexical[i] > 0 or bool(explicit)],
            key=lambda i: (-float(lexical[i]), self.chunks[i].id),
        )[:50]
        semantic_ranking = (
            sorted(allowed, key=lambda i: (-float(semantic[i]), self.chunks[i].id))[:50]
            if semantic is not None
            else []
        )
        if mode == "bm25":
            ranking = lexical_ranking
            scores = {i: float(lexical[i]) for i in ranking}
        elif mode == "semantic":
            ranking = semantic_ranking
            scores = {i: float(semantic[i]) for i in ranking}
        else:
            scores = reciprocal_rank_fusion([lexical_ranking, semantic_ranking])
            ranking = sorted(scores, key=lambda i: (-scores[i], self.chunks[i].id))
        ranks = {
            "bm25": {i: r for r, i in enumerate(lexical_ranking, start=1)},
            "semantic": {i: r for r, i in enumerate(semantic_ranking, start=1)},
        }
        seen = set()
        hits = []
        for i in ranking:
            chunk = self.chunks[i]
            if chunk.article_ref in seen:
                continue
            seen.add(chunk.article_ref)
            hits.append(
                SearchHit(
                    chunk=chunk,
                    article=self.articles[chunk.article_ref],
                    score=float(scores[i]),
                    lexical_score=float(lexical[i]),
                    semantic_score=float(semantic[i]) if semantic is not None else None,
                    ranks={name: values[i] for name, values in ranks.items() if i in values},
                )
            )
            if len(hits) == top_k:
                break
        return hits
