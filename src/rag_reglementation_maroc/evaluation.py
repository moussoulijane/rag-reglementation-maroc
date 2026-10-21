"""Article-level retrieval evaluation; generated answer faithfulness is out of scope."""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from statistics import mean
from typing import Any, Protocol

from .models import SearchHit

PROTOCOL_VERSION = "bam-10312-pilot-v1"
LANGUAGES = {"fr", "ar"}
MODES = {"bm25", "semantic", "hybrid"}


class Retriever(Protocol):
    def search(
        self,
        question: str,
        language: str | None = None,
        mode: str = "bm25",
        top_k: int = 5,
    ) -> list[SearchHit]: ...


def _validate_cases(cases: Sequence[dict[str, Any]]) -> None:
    seen_ids: set[str] = set()
    group_splits: dict[str, str] = {}
    for case in cases:
        missing = {
            "id",
            "group_id",
            "split",
            "question",
            "query_language",
            "source_language",
            "answerable",
            "expected_article_ids",
        } - case.keys()
        if missing:
            raise ValueError(f"Missing case fields: {sorted(missing)}")
        if not isinstance(case["id"], str) or not case["id"] or case["id"] in seen_ids:
            raise ValueError("Case IDs must be unique nonempty strings.")
        seen_ids.add(case["id"])
        if not isinstance(case["group_id"], str) or not case["group_id"]:
            raise ValueError("Each case needs a nonempty group_id.")
        if case["split"] not in {"dev", "test"}:
            raise ValueError("The split must be dev or test.")
        previous = group_splits.setdefault(case["group_id"], case["split"])
        if previous != case["split"]:
            raise ValueError("Translations of a topic cannot cross dev/test.")
        if not isinstance(case["question"], str) or not case["question"].strip():
            raise ValueError("Question must be nonempty.")
        if case["query_language"] not in LANGUAGES or case["source_language"] not in LANGUAGES:
            raise ValueError("Supported languages are fr and ar.")
        if not isinstance(case["answerable"], bool):
            raise ValueError("answerable must be a JSON boolean.")
        expected = case["expected_article_ids"]
        if not isinstance(expected, list) or any(not isinstance(a, str) or not a for a in expected):
            raise ValueError("Expected article IDs must be a list of nonempty strings.")
        if len(expected) != len(set(expected)):
            raise ValueError("Expected article IDs must not contain duplicates.")
        if case["answerable"] != bool(expected):
            raise ValueError("Positive cases need article IDs; negatives must have none.")


def load_cases(path: str | Path, split: str | None = None) -> list[dict[str, Any]]:
    """Validate the complete benchmark before selecting one split."""
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    cases = data["cases"] if isinstance(data, dict) else data
    if not isinstance(cases, list):
        raise ValueError("Benchmark must contain a list of cases.")
    _validate_cases(cases)
    if split is not None and split not in {"dev", "test"}:
        raise ValueError("split must be dev, test or None.")
    return [case for case in cases if split is None or case["split"] == split]


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _aggregate(rows: list[dict[str, Any]], label: str, top_k: int) -> dict[str, Any]:
    positive = [row for row in rows if row["answerable"]]
    negative = [row for row in rows if not row["answerable"]]
    decided = [row for row in rows if row["predicted_answerable"] is not None]
    result: dict[str, Any] = {
        "direction": label,
        "n_cases": len(rows),
        "n_topic_groups": len({row["group_id"] for row in rows}),
        "n_positive": len(positive),
        "n_negative": len(negative),
        f"recall_at_{top_k}": mean(row["recall_at_k"] for row in positive) if positive else None,
        f"mrr_at_{top_k}": mean(row["reciprocal_rank_at_k"] for row in positive)
        if positive
        else None,
        "mean_search_latency_ms": mean(row["search_latency_ms"] for row in rows) if rows else None,
        "coverage": None,
        "positive_answer_rate": None,
        "negative_abstention_rate": None,
        "answerability_precision": None,
        "answerability_balanced_accuracy": None,
    }
    if decided:
        tp = sum(row["answerable"] and row["predicted_answerable"] for row in decided)
        fp = sum(not row["answerable"] and row["predicted_answerable"] for row in decided)
        tn = sum(not row["answerable"] and not row["predicted_answerable"] for row in decided)
        fn = sum(row["answerable"] and not row["predicted_answerable"] for row in decided)
        positive_rate = _ratio(tp, tp + fn)
        negative_rate = _ratio(tn, tn + fp)
        result.update(
            coverage=_ratio(tp + fp, len(decided)),
            positive_answer_rate=positive_rate,
            negative_abstention_rate=negative_rate,
            answerability_precision=_ratio(tp, tp + fp),
            answerability_balanced_accuracy=(
                (positive_rate + negative_rate) / 2
                if positive_rate is not None and negative_rate is not None
                else None
            ),
        )
    return result


def evaluate_retrieval(
    retriever: Retriever,
    cases: Sequence[dict[str, Any]],
    mode: str,
    top_k: int = 5,
    decide_answer: Callable[[str, list[SearchHit], str], bool] | None = None,
) -> dict[str, Any]:
    """Measure source retrieval, never infer factual faithfulness from a citation.

    Source language is a strict filter, distinct from the question language.
    Ranks count unique article IDs, so repeated chunks cannot inflate recall.
    Callback decisions must use development-frozen settings for test evaluation.
    """
    if mode not in MODES:
        raise ValueError(f"Unknown retrieval mode: {mode}")
    if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 1:
        raise ValueError("top_k must be a positive integer.")
    _validate_cases(cases)
    rows: list[dict[str, Any]] = []
    for case in cases:
        started = time.perf_counter()
        hits = retriever.search(
            case["question"], language=case["source_language"], mode=mode, top_k=top_k
        )
        elapsed = (time.perf_counter() - started) * 1000
        unique_hits: list[SearchHit] = []
        seen_articles: set[str] = set()
        for hit in hits:
            if hit.article.language != case["source_language"]:
                raise ValueError("Retriever returned a source outside the requested language.")
            article_id = hit.article.article_id
            if article_id not in seen_articles:
                seen_articles.add(article_id)
                unique_hits.append(hit)
            if len(unique_hits) == top_k:
                break
        predicted_ids = [hit.article.article_id for hit in unique_hits]
        expected_ids = set(case["expected_article_ids"])
        positive = case["answerable"]
        relevant_ranks = [
            rank for rank, article_id in enumerate(predicted_ids, 1) if article_id in expected_ids
        ]
        decision = decide_answer(case["question"], unique_hits, mode) if decide_answer else None
        if decide_answer is not None and not isinstance(decision, bool):
            raise ValueError("decide_answer must return a bool.")
        rows.append(
            {
                "id": case["id"],
                "question": case["question"],
                "negative_type": case.get("negative_type"),
                "group_id": case["group_id"],
                "split": case["split"],
                "query_language": case["query_language"],
                "source_language": case["source_language"],
                "direction": f"{case['query_language']}->{case['source_language']}",
                "answerable": positive,
                "expected_article_ids": case["expected_article_ids"],
                "retrieved_article_ids": predicted_ids,
                "recall_at_k": (
                    len(set(predicted_ids) & expected_ids) / len(expected_ids) if positive else None
                ),
                "reciprocal_rank_at_k": (1 / min(relevant_ranks) if relevant_ranks else 0.0)
                if positive
                else None,
                "predicted_answerable": decision,
                "search_latency_ms": elapsed,
            }
        )
    aggregate = [
        _aggregate([row for row in rows if row["direction"] == direction], direction, top_k)
        for direction in ("fr->fr", "ar->ar", "fr->ar", "ar->fr")
    ]
    populated = [item for item in aggregate if item["n_cases"]]
    overall = _aggregate(rows, "overall", top_k)
    macro: dict[str, Any] = {"direction": "macro_direction", "n_directions": len(populated)}
    metric_keys = [
        f"recall_at_{top_k}",
        f"mrr_at_{top_k}",
        "positive_answer_rate",
        "negative_abstention_rate",
        "answerability_balanced_accuracy",
    ]
    for key in metric_keys:
        values = [item[key] for item in populated if item[key] is not None]
        macro[key] = mean(values) if values else None
    fingerprint = hashlib.sha256(
        json.dumps(list(cases), ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    source_records = {}
    articles = getattr(retriever, "articles", {})
    article_values = articles.values() if isinstance(articles, dict) else articles
    for article in article_values:
        source_records[article.source_id] = {
            "source_id": article.source_id,
            "language": article.language,
            "source_url": article.source_url,
            "version_date": article.version_date,
            "pdf_sha256": article.sha256,
        }
    return {
        "rows": rows,
        "aggregate": [*aggregate, overall, macro],
        "metadata": {
            "protocol_version": PROTOCOL_VERSION,
            "retriever": getattr(retriever, "metadata", {}),
            "sources": [source_records[key] for key in sorted(source_records)],
            "mode": mode,
            "top_k": top_k,
            "cases_sha256": fingerprint,
            "n_cases": len(rows),
            "n_topic_groups": len({row["group_id"] for row in rows}),
            "splits": sorted({row["split"] for row in rows}),
            "abstention_evaluated": decide_answer is not None,
            "unit": "unique article within the requested source language",
            "uncertainty": "descriptive; translations share a topic and are not independent",
            "latency_scope": "search only; excludes model/index loading and answer generation",
            "faithfulness_evaluated": False,
        },
    }
