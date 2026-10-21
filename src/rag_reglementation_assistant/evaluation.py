"""Development diagnostics, kept separate from semantic and independent review."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from .corpus import canonical, sha


def evaluate_development(service, cases_path: Path, output: Path, mode="bm25"):
    if output.exists() and any(output.iterdir()):
        raise ValueError("Choisir un nouveau dossier de résultats ; historique conservé.")
    output.mkdir(parents=True, exist_ok=True)
    suite = json.loads(cases_path.read_text(encoding="utf-8"))
    if suite.get("status") != "development":
        raise ValueError("Cette commande exécute uniquement un diagnostic de développement.")
    source_root = Path(__file__).parent
    manifest = {
        "status": "development_not_independent_test",
        "cases_sha256": sha(cases_path.read_bytes()),
        "assistant_sources": {p.name: sha(p.read_bytes()) for p in source_root.glob("*.py")},
        "reviewed_propositions": sha((source_root / "knowledge.py").read_bytes()),
        "reviewed_source_hashes": sha(
            (source_root / "resources/reviewed_hashes.json").read_bytes()
        ),
        "legacy_retriever": service.legacy.retriever.metadata,
        "assistant_retriever": service.retriever.metadata,
        "frozen_before_execution_at": datetime.now(UTC).isoformat(),
        "mode": mode,
        "independent_legal_review": False,
    }
    (output / "manifest.json").write_bytes(canonical(manifest))
    rows = []
    for case in suite["cases"]:
        for language in ["fr", "ar"]:
            response = service.ask(
                case["questions"][language],
                mode=mode,
                source_language=case.get("source_language"),
                as_of=case.get("as_of"),
                institution_type=case.get("institution_type", "credit_institution"),
            )
            a = response["assessment"]
            found = {c["article_ref"] for c in response["citations"]}
            facts = {f["id"] for f in a.get("claims", [])}
            expected = set(case.get("expected_facts", []))
            mechanical = all(
                c["quote"] == service.articles[c["article_ref"]].text
                and c["sha256"] == service.articles[c["article_ref"]].sha256
                for c in response["citations"]
            )
            rows.append(
                {
                    "id": case["id"],
                    "language": language,
                    "expected": case["expected_status"],
                    "actual": a["status"],
                    "status_match": a["status"] == case["expected_status"],
                    "false_complete": a["status"] == "complete"
                    and case["expected_status"] != "complete",
                    "expected_fact_count": len(expected),
                    "expected_facts_found": len(expected & facts),
                    "expected_facts_present": expected <= facts,
                    "citation_count": len(response["citations"]),
                    "citations_mechanically_valid": mechanical,
                    "retrieved_articles": response["trace"]["candidate_article_ids"],
                    "evidence_articles": sorted(found),
                    "guided_expansion_articles": response["trace"][
                        "reference_expansion_article_ids"
                    ],
                    "latency_ms": response["latency_ms"],
                }
            )

    def metrics(values):
        positive = [r for r in values if r["expected"] == "complete"]
        other = [r for r in values if r["expected"] != "complete"]
        return {
            "n_cases": len(values),
            "status_matches": sum(r["status_match"] for r in values),
            "non_complete_cases": len(other),
            "false_complete": sum(r["false_complete"] for r in other),
            "complete_cases": len(positive),
            "complete_cases_with_expected_facts": sum(
                r["actual"] == "complete" and r["expected_facts_present"] for r in positive
            ),
            "all_expected_facts_present": sum(r["expected_facts_present"] for r in values),
            "citations_mechanically_valid": all(r["citations_mechanically_valid"] for r in values),
            "claim_faithfulness": "not_independently_evaluated",
            "context_semantic_sufficiency": "not_independently_evaluated",
        }

    report = {
        "status": "development_diagnostic",
        "metrics": metrics(rows),
        "by_language": {
            language: metrics([r for r in rows if r["language"] == language])
            for language in ["fr", "ar"]
        },
        "n_groups": len(suite["cases"]),
        "rows": rows,
        "limits": [
            "Questions et catalogue préparés en développement ; pas de test tenu à l’écart.",
            "La présence des faits attendus vérifie le contrat du catalogue, pas la fidélité sémantique générale.",
            "Les variantes FR/AR sont corrélées ; aucun gain universel sur V2 ne peut en être déduit.",
            "Le profil a été rétréci et le corpus élargi : comparaison causale à corpus constant requise.",
        ],
    }
    (output / "results.json").write_bytes(canonical(report))
    m = report["metrics"]
    lines = [
        "# Diagnostic de développement — assistant V3",
        "",
        f"{len(suite['cases'])} groupes, {len(rows)} variantes FR/AR, mode {mode}.",
        "",
        f"- Statut conforme aux annotations internes : {m['status_matches']}/{m['n_cases']}.",
        f"- Réponses annoncées complètes à tort : {m['false_complete']}/{m['non_complete_cases']} cas attendus non complets.",
        f"- Cas complets avec les faits attendus : {m['complete_cases_with_expected_facts']}/{m['complete_cases']}.",
        f"- Validité mécanique des citations : {m['citations_mechanically_valid']}.",
        "",
        "## Erreurs observées",
        "",
    ]
    lines += [
        f"- {r['id']} / {r['language']} : attendu {r['expected']}, obtenu {r['actual']}."
        for r in rows
        if not r["status_match"] or not r["expected_facts_present"]
    ]
    lines += ["", "## Limites", ""] + [f"- {limit}" for limit in report["limits"]]
    (output / "RESULTATS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report
