"""Describe frozen challenge errors without rewriting scores or source passages."""

import argparse
import json
from collections import Counter
from pathlib import Path


def analyze(report: dict) -> dict:
    rows = report["rows"]
    positive = [row for row in rows if row["answerable"]]
    negative = [row for row in rows if not row["answerable"]]
    return {
        "mode": report["metadata"]["mode"],
        "n_cases": len(rows),
        "n_topic_groups": len({row["group_id"] for row in rows}),
        "overall": next(item for item in report["aggregate"] if item["direction"] == "overall"),
        "positive_missing_any_expected_article": [
            row["id"] for row in positive if row["recall_at_k"] < 1
        ],
        "positive_accepted_with_incomplete_article_recall": [
            row["id"] for row in positive if row["predicted_answerable"] and row["recall_at_k"] < 1
        ],
        "positive_refused_with_full_article_recall": [
            row["id"]
            for row in positive
            if not row["predicted_answerable"] and row["recall_at_k"] == 1
        ],
        "negative_accepted": [
            {
                "id": row["id"],
                "group_id": row["group_id"],
                "direction": row["direction"],
                "negative_type": row["negative_type"],
            }
            for row in negative
            if row["predicted_answerable"]
        ],
        "negative_accepted_by_type": dict(
            Counter(
                row["negative_type"] or "unspecified"
                for row in negative
                if row["predicted_answerable"]
            )
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    reports = [
        json.loads((args.directory / f"{mode}.json").read_text(encoding="utf-8"))
        for mode in ("bm25", "semantic", "hybrid")
    ]
    assert len({report["metadata"]["cases_sha256"] for report in reports}) == 1
    assert all(
        report["metadata"]["analysis_status"] == "prospective_internal_challenge"
        for report in reports
    )
    result = {
        "scope": "Error counts on frozen internal new topics; not generated-answer accuracy.",
        "cases_sha256": reports[0]["metadata"]["cases_sha256"],
        "analyses": [analyze(report) for report in reports],
        "limits": (
            "Expected articles are internal annotations. Missing a labeled article may also "
            "reveal an incomplete gold label. Article recall does not measure passage support. "
            "Four language directions share topics; no independence confidence intervals."
        ),
    }
    lines = [
        "# Analyse des erreurs — nouveaux thèmes",
        "",
        "Les scores complets et les quatre directions sont dans [RESULTATS.md](RESULTATS.md). "
        "Les effectifs ci-dessous portent sur des couples question/langue-source corrélés.",
        "",
        "| Mode | Rappel incomplet sur positifs | Positifs acceptés avec rappel incomplet | "
        "Positifs refusés malgré rappel complet | Négatifs acceptés |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for item in result["analyses"]:
        lines.append(
            f"| {item['mode']} | {len(item['positive_missing_any_expected_article'])} | "
            f"{len(item['positive_accepted_with_incomplete_article_recall'])} | "
            f"{len(item['positive_refused_with_full_article_recall'])} | "
            f"{len(item['negative_accepted'])} |"
        )
    lines += [
        "",
        "Un article retrouvé peut ne pas contenir le passage utile dans le contexte sélectionné. "
        "Une question positive acceptée sans tous les articles annotés doit être relue ; "
        "cela ne suffit pas à conclure que la réponse aurait été fausse, car le gold peut "
        "être incomplet. Un négatif accepté signale que la garde d'abstention n'a pas reconnu "
        "l'insuffisance du corpus.",
        "",
        "## Négatifs acceptés",
        "",
    ]
    for item in result["analyses"]:
        lines += [f"### {item['mode']}", ""]
        if item["negative_accepted"]:
            lines += [
                f"- {row['group_id']} — {row['direction']} ({row['negative_type']})"
                for row in item["negative_accepted"]
            ]
        else:
            lines.append("Aucun sur ce lot.")
        lines.append("")
    lines += [
        "Conserver ces résultats avant tout changement de seuil ou de classement. "
        "Une correction motivée par ce lot rend sa prochaine exécution exploratoire. "
        "La fidélité d'une réponse générée reste une mesure distincte. "
        "Les identifiants de tous les cas concernés sont dans [error_analysis.json](error_analysis.json).",
        "",
    ]
    for name, text in [
        ("error_analysis.json", json.dumps(result, ensure_ascii=False, indent=2) + "\n"),
        ("ERREURS.md", "\n".join(lines)),
    ]:
        with (args.directory / name).open("x", encoding="utf-8") as stream:
            stream.write(text)
    print("\n".join(lines))


if __name__ == "__main__":
    main()
