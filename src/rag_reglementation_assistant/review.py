"""Freeze a reserved evaluation and require a separate semantic review.

Declarations identify review provenance; the software cannot authenticate a
person's competence or independence. No expert review is fabricated here.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from .corpus import canonical, sha


def snapshot(service):
    root = Path(__file__).parent
    files = list(root.glob("*.py")) + list((root / "resources").glob("*.json"))
    legacy = root.parent / "rag_reglementation_maroc"
    files += list(legacy.glob("*.py"))
    return {
        "sources": {str(p.relative_to(root.parent)): sha(p.read_bytes()) for p in files},
        "corpus": sha(
            canonical(
                [a.model_dump() for a in sorted(service.articles.values(), key=lambda a: a.id)]
            )
        ),
        "retriever": service.retriever.metadata,
    }


def freeze_reserved(service, cases_path: Path, manifest_path: Path, mode="semantic"):
    suite = json.loads(cases_path.read_text(encoding="utf-8"))
    declaration = suite.get("annotation_review", {})
    if (
        suite.get("status") != "reserved_test"
        or not suite.get("cases")
        or declaration.get("kind") != "external_human"
        or not declaration.get("reviewer")
        or not declaration.get("competence")
        or declaration.get("rankings_consulted") is not False
        or declaration.get("semantic_overlap_audited") is not True
        or declaration.get("independent_from_implementation") is not True
    ):
        raise ValueError(
            "Annotations réservées et déclaration de revue humaine indépendante requises."
        )
    identifiers = set()
    for case in suite["cases"]:
        if case["group_id"] in identifiers or not case.get("variants"):
            raise ValueError("Groupes dupliqués ou variantes manquantes.")
        identifiers.add(case["group_id"])
        for variant in case["variants"]:
            if (
                variant.get("query_language") not in ["fr", "ar"]
                or variant.get("source_language") not in ["fr", "ar", None]
                or variant.get("expected_status")
                not in ["complete", "partial", "absent", "temporal", "ambiguous"]
                or len(variant.get("question", "").strip()) < 3
            ):
                raise ValueError("Variante annotée invalide.")
    if manifest_path.exists():
        raise ValueError("Le manifeste réservé existe déjà.")
    manifest = {
        "status": "reserved_annotations_declared_external",
        "frozen_at": datetime.now(UTC).isoformat(),
        "mode": mode,
        "questions_sha256": sha(cases_path.read_bytes()),
        "snapshot": snapshot(service),
        "annotation_review": declaration,
        "review_identity_authenticated": False,
        "independent_output_review_completed": False,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_bytes(canonical(manifest))
    return manifest


def evaluate_reserved(
    service, cases_path: Path, manifest_path: Path, output: Path, private: Path, mode="semantic"
):
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        manifest.get("mode") != mode
        or manifest["questions_sha256"] != sha(cases_path.read_bytes())
        or manifest["snapshot"] != snapshot(service)
    ):
        raise ValueError("Questions, moteur, corpus ou modèle différents du gel.")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Nouveau dossier de résultats requis.")
    if not private.resolve().is_relative_to(Path("outputs").resolve()):
        raise ValueError("Les réponses et citations de revue doivent rester sous outputs/.")
    if private.exists() and any(private.iterdir()):
        raise ValueError("Nouveau dossier privé requis.")
    suite = json.loads(cases_path.read_text(encoding="utf-8"))
    rows, queue, review = [], [], []
    for case in suite["cases"]:
        for index, variant in enumerate(case["variants"]):
            key = f"{case['group_id']}:{index}"
            response = service.ask(
                variant["question"],
                source_language=variant.get("source_language"),
                mode=mode,
                as_of=variant.get("as_of"),
                institution_type=variant.get("institution_type", "credit_institution"),
            )
            claims = response["assessment"].get("claims", [])
            queue.append({"id": key, "question": variant["question"], "response": response})
            rows.append(
                {
                    "id": key,
                    "group_id": case["group_id"],
                    "language": variant["query_language"],
                    "expected_status": variant["expected_status"],
                    "actual_status": response["assessment"]["status"],
                    "emitted_claim_ids": [c["id"] for c in claims],
                    "citations_mechanically_valid": all(
                        c["quote"] == service.articles[c["article_ref"]].text
                        for c in response["citations"]
                    ),
                }
            )
            review.append(
                {
                    "id": key,
                    "claim_verdicts": {c["id"]: None for c in claims},
                    "coverage": None,
                    "critical_error": None,
                    "status_appropriate": None,
                    "notes": "",
                }
            )
    output.mkdir(parents=True, exist_ok=True)
    private.mkdir(parents=True, exist_ok=True)
    result = {
        "status": "reserved_run_awaiting_human_output_review",
        "mode": mode,
        "n_groups": len(suite["cases"]),
        "rows": rows,
        "manifest_sha256": sha(manifest_path.read_bytes()),
        "semantic_fidelity": "not_yet_evaluated",
        "all_release_gates_passed": False,
    }
    (output / "results.json").write_bytes(canonical(result))
    (private / "responses.json").write_bytes(canonical(queue))
    (private / "review-template.json").write_bytes(
        canonical(
            {
                "reviewer": "",
                "competence": "",
                "independent_from_implementation": None,
                "rows": review,
            }
        )
    )
    return result


def import_review(results_path: Path, review_path: Path, output: Path):
    result = json.loads(results_path.read_text(encoding="utf-8"))
    review = json.loads(review_path.read_text(encoding="utf-8"))
    if (
        not review.get("reviewer")
        or not review.get("competence")
        or review.get("independent_from_implementation") is not True
    ):
        raise ValueError("Provenance de la revue des sorties manquante.")
    expected = {row["id"]: row for row in result["rows"]}
    received = {row["id"]: row for row in review["rows"]}
    if len(received) != len(review["rows"]) or set(received) != set(expected):
        raise ValueError("Toutes les sorties doivent être relues sans sélection.")
    verdicts = []
    coverages = []
    critical = 0
    for key, row in received.items():
        claims = row["claim_verdicts"]
        if set(claims) != set(expected[key]["emitted_claim_ids"]):
            raise ValueError("Affirmations omises ou ajoutées.")
        if any(
            v not in ["supported", "contradicted", "not_supported", "unverifiable"]
            for v in claims.values()
        ):
            raise ValueError("Affirmations non relues.")
        if not isinstance(row["critical_error"], bool) or not isinstance(
            row["status_appropriate"], bool
        ):
            raise ValueError("Gravité et statut doivent être relus.")
        if not isinstance(row["coverage"], (int, float)) or not 0 <= row["coverage"] <= 1:
            raise ValueError("Couverture entre 0 et 1 requise.")
        verdicts.extend(claims.values())
        coverages.append(row["coverage"])
        critical += row["critical_error"]
    summary = {
        "status": "human_review_imported_declaration_not_authenticated",
        "reviewer": review["reviewer"],
        "n_outputs": len(received),
        "n_claims": len(verdicts),
        "supported_claims": verdicts.count("supported"),
        "critical_errors": critical,
        "mean_coverage": sum(coverages) / len(coverages) if coverages else None,
        "claim_support_rate": verdicts.count("supported") / len(verdicts) if verdicts else None,
        "scope": "This review does not alone validate current law or all release gates.",
        "review_sha256": sha(review_path.read_bytes()),
        "results_sha256": sha(results_path.read_bytes()),
    }
    if output.exists():
        raise ValueError("Rapport de revue déjà présent.")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical(summary))
    return summary
