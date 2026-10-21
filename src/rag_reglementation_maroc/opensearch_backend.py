"""Optional OpenSearch adapter with explicit, provenance-checked indexing.

No cluster write occurs during construction or search. ``index()`` is the only
indexing operation; it never deletes an existing index.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any

import numpy as np

from .models import Article, Chunk, SearchHit
from .retrieval import reciprocal_rank_fusion
from .text import requested_articles


def _fuse(rankings: dict[str, list[str]], constant: int = 60) -> dict[str, float]:
    identifiers = list(dict.fromkeys(item for ranking in rankings.values() for item in ranking))
    positions = {identifier: position for position, identifier in enumerate(identifiers)}
    scores = reciprocal_rank_fusion(
        [[positions[item] for item in dict.fromkeys(ranking)] for ranking in rankings.values()],
        constant,
    )
    return {identifiers[position]: score for position, score in scores.items()}


class OpenSearchRetriever:
    """Search the same original chunks as the local retriever.

    RRF is computed in this adapter from two candidate lists. This avoids a
    hidden cluster-wide search pipeline and keeps fusion identical in principle
    to the local backend. OpenSearch still performs BM25 and neural k-NN search.
    """

    def __init__(
        self,
        articles: list[Article],
        chunks: list[Chunk],
        encoder: Any = None,
        *,
        client: Any = None,
        url: str | None = None,
        index_name: str | None = None,
    ) -> None:
        self.articles = {article.id: article for article in articles}
        self.chunks = {chunk.id: chunk for chunk in chunks}
        if not self.articles or not self.chunks:
            raise ValueError("Le corpus et ses passages ne peuvent pas être vides.")
        if len(self.articles) != len(articles) or len(self.chunks) != len(chunks):
            raise ValueError("Les identifiants d'articles et de passages doivent être uniques.")
        for chunk in chunks:
            article = self.articles.get(chunk.article_ref)
            if article is None or article.text[chunk.char_start : chunk.char_end] != chunk.text:
                raise ValueError("Un passage doit correspondre exactement à son article source.")
        self.encoder = encoder
        provenance = {
            "schema": 1,
            "articles": [article.model_dump() for article in sorted(articles, key=lambda x: x.id)],
            "chunks": [chunk.model_dump() for chunk in sorted(chunks, key=lambda x: x.id)],
            "encoder": encoder.metadata if encoder is not None else None,
        }
        self.fingerprint = hashlib.sha256(
            json.dumps(provenance, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        self.index_name = index_name or f"bam-banking-law-{self.fingerprint[:16]}"
        if client is None:
            try:
                from opensearchpy import OpenSearch
            except ImportError as exc:
                raise RuntimeError(
                    "Installer l'option opensearch : pip install '.[opensearch]'."
                ) from exc
            client = OpenSearch(
                hosts=[url or os.environ.get("OPENSEARCH_URL", "http://127.0.0.1:9200")],
                timeout=30,
                max_retries=0,
                retry_on_timeout=False,
            )
        self.client = client

    @property
    def metadata(self) -> dict:
        return {
            "backend": "opensearch",
            "index": self.index_name,
            "fingerprint": self.fingerprint,
            "fusion": "client-side reciprocal rank fusion",
            "rrf_constant": 60,
            "candidate_k": 50,
            "article_count": len(self.articles),
            "chunk_count": len(self.chunks),
            "encoder": self.encoder.metadata if self.encoder is not None else None,
        }

    def _check_existing_index(self) -> None:
        mapping = self._service_call(self.client.indices.get_mapping, index=self.index_name)
        fingerprint = (
            mapping[self.index_name].get("mappings", {}).get("_meta", {}).get("fingerprint")
        )
        if fingerprint != self.fingerprint:
            raise RuntimeError(
                "L'index OpenSearch ne correspond pas au corpus/modèle local ; "
                "utiliser un nouvel index et une indexation explicite."
            )

    def check_ready(self) -> None:
        """Verify cluster/index provenance without writing or creating anything."""
        self._check_existing_index()

    @staticmethod
    def _service_call(method, **kwargs):
        try:
            return method(**kwargs)
        except Exception as exc:
            raise RuntimeError(
                "OpenSearch indisponible ou index non préparé ; vérifier le service "
                "puis lancer une indexation explicite."
            ) from exc

    def index(self) -> dict:
        """Create or update this exact snapshot; never delete an index."""
        properties = {
            "chunk_id": {"type": "keyword"},
            "article_ref": {"type": "keyword"},
            "article_id": {"type": "keyword"},
            "language": {"type": "keyword"},
            "text": {"type": "text", "analyzer": "bilingual"},
            "char_start": {"type": "integer"},
            "char_end": {"type": "integer"},
        }
        if self.encoder is not None:
            properties["embedding"] = {
                "type": "knn_vector",
                "dimension": 384,
                "method": {
                    "name": "hnsw",
                    "space_type": "cosinesimil",
                    "engine": "lucene",
                    "parameters": {"ef_construction": 128, "m": 16},
                },
            }
        body = {
            "settings": {
                "index": {"knn": self.encoder is not None, "number_of_replicas": 0},
                "analysis": {
                    "analyzer": {
                        "bilingual": {
                            "type": "custom",
                            "tokenizer": "standard",
                            "filter": ["lowercase", "asciifolding", "arabic_normalization"],
                        }
                    }
                },
            },
            "mappings": {
                "_meta": {"fingerprint": self.fingerprint, "schema": 1},
                "properties": properties,
            },
        }
        if self._service_call(self.client.indices.exists, index=self.index_name):
            self._check_existing_index()
        else:
            self._service_call(self.client.indices.create, index=self.index_name, body=body)
        chunks = list(self.chunks.values())
        for batch_start in range(0, len(chunks), 100):
            batch = chunks[batch_start : batch_start + 100]
            vectors = (
                self.encoder.encode_documents([chunk.text for chunk in batch])
                if self.encoder is not None
                else None
            )
            actions = []
            for position, chunk in enumerate(batch):
                article = self.articles[chunk.article_ref]
                document = {
                    "chunk_id": chunk.id,
                    "article_ref": chunk.article_ref,
                    "article_id": article.article_id,
                    "language": article.language,
                    "text": chunk.text,
                    "char_start": chunk.char_start,
                    "char_end": chunk.char_end,
                }
                if vectors is not None:
                    vector = np.asarray(vectors[position], dtype=np.float32)
                    if vector.shape != (384,) or not np.isfinite(vector).all():
                        raise RuntimeError(
                            "Le vecteur OpenSearch doit avoir 384 dimensions finies."
                        )
                    document["embedding"] = vector.tolist()
                actions.extend([{"index": {"_index": self.index_name, "_id": chunk.id}}, document])
            result = self._service_call(self.client.bulk, body=actions, refresh=True)
            if result.get("errors", False):
                raise RuntimeError("OpenSearch signale des erreurs d'indexation ; index incomplet.")
        return {"index": self.index_name, "chunks": len(chunks), "fingerprint": self.fingerprint}

    def _run_query(self, query: dict, size: int) -> list[dict]:
        result = self._service_call(
            self.client.search, index=self.index_name, body={"size": size, "query": query}
        )
        hits = result.get("hits", {}).get("hits", [])
        for hit in hits:
            identifier = hit.get("_id")
            source = hit.get("_source", {})
            if identifier not in self.chunks:
                raise RuntimeError("L'index a renvoyé un passage absent du corpus local.")
            chunk = self.chunks[identifier]
            if source.get("text") != chunk.text or source.get("article_ref") != chunk.article_ref:
                raise RuntimeError("Le passage OpenSearch diffère du passage local vérifié.")
        return hits

    def search(
        self,
        question: str,
        language: str | None = None,
        mode: str = "bm25",
        top_k: int = 5,
    ) -> list[SearchHit]:
        if not question.strip():
            raise ValueError("La question ne peut pas être vide.")
        if language not in (None, "fr", "ar"):
            raise ValueError("language doit être fr, ar ou None.")
        if mode not in ("bm25", "semantic", "hybrid"):
            raise ValueError("Mode inconnu : bm25, semantic ou hybrid.")
        if not 1 <= top_k <= 20:
            raise ValueError("top_k doit être compris entre 1 et 20.")
        if mode != "bm25" and self.encoder is None:
            raise ValueError("Le mode sémantique/hybride nécessite un encodeur explicite.")
        explicit = requested_articles(question)
        allowed = {
            article.id
            for article in self.articles.values()
            if (language is None or article.language == language)
            and (not explicit or article.article_id in explicit)
        }
        if not allowed:
            return []
        # Checking is read-only and detects an edited index before citing results.
        self._check_existing_index()
        size = min(sum(chunk.article_ref in allowed for chunk in self.chunks.values()), 50)
        filters = []
        if language:
            filters.append({"term": {"language": language}})
        if explicit:
            filters.append(
                {"term": {"article_id": explicit[0]}}
                if len(explicit) == 1
                else {"terms": {"article_id": explicit}}
            )
        rankings: dict[str, list[str]] = {}
        lexical_scores: dict[str, float] = {}
        semantic_scores: dict[str, float] = {}
        if mode in ("bm25", "hybrid"):
            match = {"match": {"text": {"query": question}}}
            if explicit:
                query = {"bool": {"should": [match], "minimum_should_match": 0, "filter": filters}}
            else:
                query = {"bool": {"must": [match], "filter": filters}} if filters else match
            hits = self._run_query(query, size)
            rankings["bm25"] = [hit["_id"] for hit in hits]
            lexical_scores = {hit["_id"]: float(hit["_score"]) for hit in hits}
        if mode in ("semantic", "hybrid"):
            vector = np.asarray(self.encoder.encode_query(question), dtype=np.float32)
            if vector.shape != (384,) or not np.isfinite(vector).all():
                raise RuntimeError("Le vecteur de question est invalide.")
            parameters = {"vector": vector.tolist(), "k": size}
            if filters:
                parameters["filter"] = (
                    filters[0] if len(filters) == 1 else {"bool": {"filter": filters}}
                )
            hits = self._run_query({"knn": {"embedding": parameters}}, size)
            rankings["semantic"] = [hit["_id"] for hit in hits]
            for hit in hits:
                document_vector = np.asarray(hit["_source"].get("embedding", []), dtype=np.float32)
                if document_vector.shape != (384,) or not np.isfinite(document_vector).all():
                    raise RuntimeError("L'index ne contient pas le vecteur attendu.")
                denominator = float(np.linalg.norm(vector) * np.linalg.norm(document_vector))
                if denominator <= 0:
                    raise RuntimeError("L'index contient un vecteur nul.")
                semantic_scores[hit["_id"]] = float(np.dot(vector, document_vector) / denominator)
        scores = (
            _fuse(rankings)
            if mode == "hybrid"
            else lexical_scores
            if mode == "bm25"
            else semantic_scores
        )
        ranks = {
            name: {identifier: rank for rank, identifier in enumerate(ids, start=1)}
            for name, ids in rankings.items()
        }
        answer = []
        seen_articles = set()
        for identifier in sorted(scores, key=lambda key: (-scores[key], key)):
            chunk = self.chunks[identifier]
            article = self.articles[chunk.article_ref]
            if language and article.language != language:
                raise RuntimeError("OpenSearch n'a pas respecté le filtre de langue.")
            if article.id not in allowed:
                raise RuntimeError("OpenSearch n'a pas respecté le filtre d'article.")
            if article.id in seen_articles:
                continue
            seen_articles.add(article.id)
            answer.append(
                SearchHit(
                    chunk=chunk,
                    article=article,
                    score=scores[identifier],
                    lexical_score=lexical_scores.get(identifier),
                    semantic_score=semantic_scores.get(identifier),
                    ranks={
                        name: values[identifier]
                        for name, values in ranks.items()
                        if identifier in values
                    },
                )
            )
            if len(answer) == top_k:
                break
        return answer
