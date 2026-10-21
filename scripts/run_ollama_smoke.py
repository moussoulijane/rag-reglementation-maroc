"""Four heterogeneous local probes; source-bearing diagnostics stay under outputs/."""

import argparse
import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from shutil import copy2

import httpx

from rag_reglementation_maroc.runtime import Settings, build_service

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = (
    {
        "case_type": "generic",
        "query_language": "fr",
        "mode": "hybrid",
        "question": "Qui accorde l'agrément avant de commencer une activité bancaire ?",
    },
    {
        "case_type": "generic",
        "query_language": "ar",
        "mode": "hybrid",
        "question": "من يمنح الاعتماد قبل مزاولة النشاط البنكي؟",
    },
    {
        "case_type": "article_targeted",
        "query_language": "fr",
        "mode": "bm25",
        "question": "Dans l'édition du 31 mars 2022, que prévoit l'article 151 sur la convention écrite à l'ouverture d'un compte et la copie remise au client ?",
    },
    {
        "case_type": "article_targeted",
        "query_language": "ar",
        "mode": "bm25",
        "question": "في نسخة 31 مارس 2022، ماذا تنص المادة 151 بخصوص الاتفاقية المكتوبة عند فتح الحساب وتسليم نسخة للعميل؟",
    },
)


def preserve_first_run(root: Path) -> None:
    """Archive existing first-run files once, without overwriting an archive."""
    for source_name, archive_name in (
        ("reports/ollama_smoke.json", "reports/ollama_smoke_v1.json"),
        ("outputs/ollama_smoke_raw.json", "outputs/ollama_smoke_raw_v1.json"),
    ):
        source, archive = root / source_name, root / archive_name
        if source.is_file() and not archive.exists():
            copy2(source, archive)


def public_example(row: dict) -> dict:
    """Allowlist original questions and metadata; never copy answers or quotes."""
    result = row["result"]
    return {
        "case_type": row["case_type"],
        "query_language": row["query_language"],
        "mode": row["mode"],
        "execution_stage": row["execution_stage"],
        "question": row["question"],
        "status": result["status"],
        "reason": result["reason"],
        "citation_article_ids": [item["article_id"] for item in result["citations"]],
        "citation_count": len(result["citations"]),
        "citation_validation": "passed" if result["citations"] else "not_applicable",
        "semantic_faithfulness": "not_evaluated",
        "latency_ms": result["latency_ms"],
    }


def retained_generic_rows(root: Path) -> list[dict]:
    """Retain both previous generic outcomes instead of replacing failures."""
    previous = json.loads((root / "outputs/ollama_smoke_raw.json").read_text(encoding="utf-8"))
    rows = []
    for example in (entry for entry in EXAMPLES if entry["case_type"] == "generic"):
        matches = [row for row in previous if row["question"] == example["question"]]
        if len(matches) != 1:
            raise ValueError(
                "Each prior generic case must exist exactly once before targeted-only."
            )
        rows.append(
            {
                **deepcopy(matches[0]),
                **example,
                "execution_stage": "retained_prior_generic",
            }
        )
    return rows


def write_reports(root: Path, raw: list[dict], report: dict) -> None:
    for path, value in (
        (root / "outputs/ollama_smoke_raw.json", raw),
        (root / "reports/ollama_smoke.json", report),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(targeted_only: bool = False):
    preserve_first_run(ROOT)
    # Fail before a model call if the two previous generic cases are missing.
    raw = retained_generic_rows(ROOT) if targeted_only else []
    settings = Settings(
        data_dir=ROOT / "data",
        encoder="multilingual",
        policy_path=ROOT / "evaluation/abstention_policy.json",
    )
    service = build_service(settings)
    for example in EXAMPLES:
        if targeted_only and example["case_type"] != "article_targeted":
            continue
        service.ollama.reset_diagnostics()
        result = service.ask(
            example["question"],
            source_language=example["query_language"],
            mode=example["mode"],
            generator="ollama",
        )
        row = {
            **example,
            "execution_stage": "current_run",
            "result": result,
            "provider_stats": deepcopy(service.ollama.last_stats),
            "provider_generation": deepcopy(service.ollama.last_generation),
        }
        raw.append(row)
        print(json.dumps(public_example(row), ensure_ascii=False), flush=True)
    with httpx.Client(trust_env=False) as client:
        response = client.get(settings.ollama_url + "/api/tags")
        response.raise_for_status()
        tags = response.json()
    model = next(
        (model for model in tags["models"] if model["name"] == settings.ollama_model),
        {},
    )
    report = {
        "scope": "four heterogeneous local integration probes, not a generated-faithfulness benchmark",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "generator": settings.ollama_model,
        "model_digest": model.get("digest"),
        "policy": service.policy_status,
        "examples": [public_example(row) for row in raw],
        "conditions": (
            "Generic questions use hybrid retrieval. Article-targeted BM25 questions explicitly "
            "name article 151 and the 2022 edition. These heterogeneous probes have no aggregate "
            "performance rate. Retained prior cases predate the final generation-context changes."
        ),
        "human_semantic_review": "not_scored",
        "source_text_redistributed": False,
        "provider_diagnostics": "local ignored outputs only",
    }
    write_reports(ROOT, raw, report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Local Ollama integration probes, not a benchmark."
    )
    parser.add_argument(
        "--targeted-only",
        action="store_true",
        help="Run two article-targeted probes and retain both previous generic outcomes.",
    )
    main(targeted_only=parser.parse_args().targeted_only)
