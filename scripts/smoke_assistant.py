"""Local HTTP integration probes; no claim of independent answer quality."""

import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Choose a new report path.")

    def request(path, data=None):
        payload = json.dumps(data, ensure_ascii=False).encode() if data else None
        req = Request(
            args.base_url + path, data=payload, headers={"Content-Type": "application/json"}
        )
        with urlopen(req, timeout=120) as response:
            return json.load(response)

    config = request("/assistant/config")
    assert config["ready"] and config["profile"]["domain_loaded"]
    assert config["profile"]["current_law_verified"] is False
    assert config["profile"]["generation_enabled"] is False
    assert config["article_count"] == 418 and config["article_count_by_language"] == {
        "fr": 221,
        "ar": 197,
    }
    probes = [
        ("fr-note", "Quel délai de réponse à une réclamation ?", {}, "complete"),
        ("ar-note", "ما أجل معالجة طلب وساطة مقبول؟", {}, "complete"),
        (
            "partial",
            "Quel délai de réponse à une réclamation et quel montant d’indemnisation ?",
            {},
            "partial",
        ),
        ("absent", "Quel montant d’indemnisation pour une réclamation ?", {}, "absent"),
        (
            "temporal",
            "Quel délai de réponse à une réclamation ?",
            {"as_of": "2026-10-21"},
            "temporal",
        ),
        ("ambiguous", "Quel délai pour une réclamation ?", {}, "ambiguous"),
        ("ar-filter", "ما أجل الرد على الشكاية؟", {"source_language": "ar"}, "absent"),
        (
            "unknown-institution",
            "Quel délai de réponse à une réclamation ?",
            {"institution_type": "unknown"},
            "ambiguous",
        ),
        ("lookup", "article 157", {}, "complete"),
    ]
    rows = []
    for id, question, options, expected in probes:
        response = request("/assistant/ask", {"question": question, "mode": "bm25", **options})
        assert response["assessment"]["status"] == expected, (id, response["assessment"]["status"])
        if expected in ["absent", "temporal", "ambiguous"]:
            assert response["citations"] == []
        if id == "fr-note":
            assert response["citations"][0]["document_id"] == "circular-10-w-2016"
            assert response["citations"][0]["page_start"] == 1146
            assert response["citations"][0]["version_date"] == "2023-12"
        if id == "ar-note":
            assert response["query_language"] == "ar" and response["source_languages"] == ["fr"]
            assert response["citations"][0]["article_id"] == "5"
        rows.append(
            {
                "id": id,
                "expected": expected,
                "actual": response["assessment"]["status"],
                "citation_count": len(response["citations"]),
                "latency_ms": response["latency_ms"],
            }
        )
    legacy = request("/ask", {"question": "article 157", "mode": "bm25"})
    assert legacy["status"] == "evidence_found"
    report = {
        "status": "passed",
        "kind": "integration_smoke_not_quality_benchmark",
        "base_url": args.base_url,
        "engine_version": config["engine_version"],
        "corpus_label": config["corpus_label"],
        "article_count": config["article_count"],
        "probes": rows,
        "legacy_endpoint_preserved": True,
        "independent_legal_review": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {"status": report["status"], "probes": len(rows), "articles": config["article_count"]}
        )
    )


if __name__ == "__main__":
    main()
