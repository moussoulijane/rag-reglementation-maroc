"""Run contract checks against an explicitly started local OpenSearch cluster.

This script creates only p2-smoke-* indexes and never deletes an index or volume.
The report contains identifiers/checks/provenance, never corpus text or excerpts.
It is an integration smoke, not a relevance or legal-accuracy benchmark.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import time
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from urllib.parse import urlsplit

from opensearchpy import OpenSearch

from rag_reglementation_maroc.chunking import build_chunks
from rag_reglementation_maroc.embeddings import MultilingualEncoder
from rag_reglementation_maroc.ingestion import load_articles
from rag_reglementation_maroc.models import Article, SearchHit
from rag_reglementation_maroc.opensearch_backend import OpenSearchRetriever


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _synthetic_articles() -> list[Article]:
    texts = {
        "fr": {
            "1": "Document synthétique de test. Une banque doit obtenir un agrément préalable.",
            "2": "Document synthétique de test. Les dépôts des clients sont enregistrés par la banque.",
            "151": "Document synthétique de test. Le secret bancaire protège les informations des clients.",
            "155": "Document synthétique de test. La protection des dépôts relève d'un mécanisme distinct.",
        },
        "ar": {
            "1": "وثيقة اصطناعية للاختبار. يجب على البنك الحصول على ترخيص مسبق لممارسة نشاطه.",
            "2": "وثيقة اصطناعية للاختبار. يسجل البنك الودائع التي يتلقاها من العملاء.",
            "151": "وثيقة اصطناعية للاختبار. يحمي السر المهني المعلومات المتعلقة بعملاء البنك.",
            "155": "وثيقة اصطناعية للاختبار. تخضع حماية الودائع لآلية مستقلة عن الترخيص.",
        },
    }
    articles = []
    for language, records in texts.items():
        for number, text in records.items():
            source_id = f"synthetic-smoke-{language}"
            articles.append(
                Article(
                    id=f"{source_id}:article-{number}",
                    document_id=f"{source_id}-v1",
                    source_id=source_id,
                    article_id=number,
                    language=language,
                    title=f"Synthetic smoke {number}",
                    text=text,
                    source_url="https://example.invalid/synthetic-test-only",
                    page_start=1,
                    page_end=1,
                    version_date="2022-03-31",
                    sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                )
            )
    return articles


def _check_hits(
    hits: list[SearchHit],
    retriever: OpenSearchRetriever,
    *,
    language: str,
    expected_articles: set[str] | None = None,
) -> None:
    assert hits, "Search did not return any hits."
    assert len({hit.article.id for hit in hits}) == len(hits), "Articles were not deduplicated."
    for hit in hits:
        original = retriever.articles[hit.article.id]
        assert hit.article.model_dump() == original.model_dump(), "Article provenance changed."
        assert hit.article.language == language, "Source-language filter was not respected."
        assert hit.chunk.text == original.text[hit.chunk.char_start : hit.chunk.char_end], (
            "Source offsets changed."
        )
        assert hit.chunk.article_ref == original.id
        assert math.isfinite(hit.score)
        if hit.semantic_score is not None:
            assert -1.00001 <= hit.semantic_score <= 1.00001, "Invalid cosine score."
    if expected_articles is not None:
        assert {hit.article.article_id for hit in hits} == expected_articles, (
            "Article filter failed."
        )


def _exercise(
    articles: list[Article],
    encoder: MultilingualEncoder | None,
    client: OpenSearch,
    scope: str,
    record: dict,
) -> None:
    started = time.perf_counter()
    chunks = build_chunks(articles, encoder)
    retriever = OpenSearchRetriever(articles, chunks, encoder, client=client)
    retriever.index_name = f"p2-smoke-{scope}-{retriever.fingerprint[:16]}"
    existed = client.indices.exists(index=retriever.index_name)
    result = retriever.index()
    retriever.check_ready()
    count = client.count(index=retriever.index_name)["count"]
    assert count == len(chunks), "Indexed document count differs from the local chunk count."
    record.update(
        {
            "index": result["index"],
            "fingerprint": result["fingerprint"],
            "index_preexisted": existed,
            "articles": len(articles),
            "chunks": count,
            "index_seconds": round(time.perf_counter() - started, 3),
            "checks": [],
        }
    )
    print(f"{scope}: {len(articles)} articles, {count} chunks indexed", flush=True)

    queries = [
        ("french", "fr", "Quelles sont les conditions d'agrément d'une banque ?", None),
        ("arabic", "ar", "ما هي شروط الترخيص لمؤسسة ائتمان؟", None),
        ("cross_fr_ar", "ar", "Quelles sont les conditions d'agrément d'une banque ?", None),
        ("cross_ar_fr", "fr", "ما هي شروط الترخيص لمؤسسة ائتمان؟", None),
        ("multi_fr", "fr", "Que disent les articles 151 et 155 ?", {"151", "155"}),
        ("multi_ar", "ar", "ما نص المادتين ١٥١ و١٥٥ ؟", {"151", "155"}),
        ("single_fr", "fr", "Quel est le texte de l'article 1 ?", {"1"}),
    ]
    modes = ["bm25"] if encoder is None else ["bm25", "semantic", "hybrid"]
    for mode in modes:
        for label, language, question, expected in queries:
            # Lexical cross-language matching is not guaranteed and is not a
            # contract of BM25. Cross-language smoke uses actual neural search.
            if label.startswith("cross_") and mode == "bm25":
                continue
            query_started = time.perf_counter()
            hits = retriever.search(question, language=language, mode=mode, top_k=5)
            _check_hits(hits, retriever, language=language, expected_articles=expected)
            record["checks"].append(
                {
                    "case": label,
                    "mode": mode,
                    "source_language": language,
                    "status": "passed",
                    "result_count": len(hits),
                    "article_ids": [hit.article.id for hit in hits],
                    "elapsed_ms": round(1000 * (time.perf_counter() - query_started), 3),
                }
            )

    # The same index name with changed source provenance must be refused before
    # any writes. No original document or index is changed by this check.
    modified = list(articles)
    modified[0] = modified[0].model_copy(update={"sha256": "0" * 64})
    mismatch = OpenSearchRetriever(
        modified, chunks, encoder, client=client, index_name=retriever.index_name
    )
    try:
        mismatch.index()
    except RuntimeError as error:
        assert "corpus/modèle" in str(error), "Mismatch failed for an unrelated reason."
    else:
        raise AssertionError("Index provenance mismatch was not rejected.")
    record["mismatch_guard"] = "passed"
    record["status"] = "passed"
    record["total_seconds"] = round(time.perf_counter() - started, 3)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:9200")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--report", type=Path, default=Path("reports/opensearch_smoke.json"))
    parser.add_argument("--include-corpus", action="store_true")
    parser.add_argument("--wait-seconds", type=float, default=60)
    args = parser.parse_args()
    if urlsplit(args.url).hostname not in {"127.0.0.1", "localhost", "::1"}:
        parser.error("This smoke script only targets a local loopback cluster.")
    report = {
        "schema_version": 1,
        "started_utc": _now(),
        "url": args.url,
        "kind": "integration-contract-smoke-not-a-relevance-benchmark",
        "python": platform.python_version(),
        "opensearch_py": version("opensearch-py"),
        "corpus_text_in_report": False,
        "service_lifecycle": "externally managed; this script never deletes or stops services",
        "resume_command": "docker compose --profile search up -d opensearch",
        "rerun_command": "python scripts/smoke_opensearch.py --include-corpus",
        "stop_command": "docker compose --profile search stop opensearch",
        "checks": {},
    }
    exit_code = 1
    try:
        client = OpenSearch(hosts=[args.url], timeout=10, max_retries=0, retry_on_timeout=False)
        deadline = time.monotonic() + args.wait_seconds
        while True:
            try:
                info = client.info()
                break
            except Exception:
                if time.monotonic() >= deadline:
                    raise RuntimeError("Local OpenSearch did not become ready in time.") from None
                time.sleep(2)
        report["cluster_version"] = info["version"]["number"]
        assert report["cluster_version"] == "3.9.0", "Unexpected OpenSearch version."
        report["cluster_health"] = client.cluster.health(wait_for_status="yellow")["status"]
        synthetic = _synthetic_articles()
        report["checks"]["synthetic_bm25"] = {}
        _exercise(synthetic, None, client, "synthetic-bm25", report["checks"]["synthetic_bm25"])
        encoder = MultilingualEncoder(args.data_dir / "models", preprocessing="normalized")
        report["encoder"] = encoder.metadata
        report["checks"]["synthetic_neural"] = {}
        _exercise(
            synthetic, encoder, client, "synthetic-neural", report["checks"]["synthetic_neural"]
        )
        if args.include_corpus:
            articles = load_articles(args.data_dir / "processed" / "articles.jsonl")
            report["source_versions"] = sorted({article.version_date for article in articles})
            report["source_sha256"] = sorted({article.sha256 for article in articles})
            report["checks"]["real_corpus"] = {}
            _exercise(articles, encoder, client, "real-corpus", report["checks"]["real_corpus"])
        report["status"] = "passed"
        exit_code = 0
    except Exception as error:
        report["status"] = "failed"
        report["error_type"] = type(error).__name__
        # No transport body or source-bearing exception goes into the report.
        report["error"] = "An integration contract failed; inspect the local execution output."
        raise
    finally:
        report["finished_utc"] = _now()
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"Smoke report: {args.report} ({report['status']})", flush=True)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
