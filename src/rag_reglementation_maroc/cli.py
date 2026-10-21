"""Commandes reproductibles, sans téléchargement au lancement de l'API."""

import argparse
import hashlib
import json
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path

from .answering import AbstentionPolicy, AnswerService
from .evaluation import evaluate_retrieval, load_cases
from .evaluation_manifest import ANALYSIS_STATUS, validate_manifest
from .ingestion import download_sources, ingest_sources
from .runtime import Settings, build_retriever, build_service

# Project assets are resolved from the documented working directory, including in Docker.
ROOT = Path.cwd()


def dump_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def signature(retriever) -> str:
    return hashlib.sha256(
        json.dumps(retriever.metadata, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def benchmark_hash(path: Path) -> str:
    cases = load_cases(path)
    return hashlib.sha256(
        json.dumps(cases, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def calibrate(retriever, questions: Path, output: Path, top_k=5) -> dict:
    cases = load_cases(questions, split="dev")
    if not cases or not any(c["answerable"] for c in cases) or all(c["answerable"] for c in cases):
        raise ValueError("La calibration exige des positifs et négatifs de développement.")
    modes = ["bm25", "semantic", "hybrid"] if retriever.encoder is not None else ["bm25"]
    chosen = {}
    grid = []
    for mode in modes:
        saved = [
            (
                case,
                retriever.search(
                    case["question"],
                    language=case["source_language"],
                    mode=mode,
                    top_k=top_k,
                ),
            )
            for case in cases
        ]
        candidates = []
        for step in range(21):
            threshold = step / 20
            policy = AbstentionPolicy(
                **{
                    "lexical_threshold"
                    if mode == "bm25"
                    else (
                        "semantic_threshold" if mode == "semantic" else "hybrid_threshold"
                    ): threshold
                }
            )
            service = AnswerService(retriever, policy)
            predictions = [
                (case["answerable"], service.accepts(case["question"], hits, mode))
                for case, hits in saved
            ]
            positive_rate = sum(y and p for y, p in predictions) / sum(y for y, p in predictions)
            negative_rate = sum(not y and not p for y, p in predictions) / sum(
                not y for y, p in predictions
            )
            row = {
                "mode": mode,
                "threshold": threshold,
                "positive_answer_rate": positive_rate,
                "negative_abstention_rate": negative_rate,
                "balanced_accuracy": (positive_rate + negative_rate) / 2,
            }
            candidates.append(row)
            grid.append(row)
        best = max(
            candidates,
            key=lambda r: (
                r["balanced_accuracy"],
                r["negative_abstention_rate"],
                r["threshold"],
            ),
        )
        chosen[mode] = best["threshold"]
    policy = AbstentionPolicy(
        lexical_threshold=chosen["bm25"],
        semantic_threshold=chosen.get("semantic", 0.45),
        hybrid_threshold=chosen.get("hybrid", 0.45),
    )
    result = {
        "status": "development_calibrated",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "policy": asdict(policy),
        "benchmark_sha256": benchmark_hash(questions),
        "retriever_signature": signature(retriever),
        "retriever": retriever.metadata,
        "development_groups": sorted({c["group_id"] for c in cases}),
        "n_development_cases": len(cases),
        "selection": "maximize balanced accuracy; ties: higher negative abstention, higher threshold",
        "candidate_grid": grid,
        "limits": "Small internal development set; translations are linked, not independent.",
    }
    dump_json(output, result)
    return result


def write_results(reports: list[dict], directory: Path, split: str, policy: dict):
    directory.mkdir(parents=True, exist_ok=True)
    status = reports[0]["metadata"].get("analysis_status", "descriptive_pilot")
    scope_note = (
        "**Analyse exploratoire après consultation du premier test.** Le correctif de "
        "normalisation arabe a été motivé par les erreurs de la première exécution. "
        "Les mêmes thèmes sont réutilisés : ce diagnostic ne constitue pas une nouvelle "
        "validation sur des questions inconnues. Les seuils sont choisis sur développement."
        if status == "exploratory_after_initial_test"
        else (
            "**Nouveaux thèmes internes, politique figée transférée sans recalibration.** "
            "Questions et code gelés après audit interne et avant exécution. "
            "Ce jeu ne bénéficie pas d'une annotation juridique externe indépendante. "
            "Les traductions restent corrélées ; les scores sont descriptifs."
            if status == ANALYSIS_STATUS
            else "Première évaluation pilote descriptive, selon le split annoncé."
        )
    )
    lines = [
        "# Résultats pilotes : recherche bancaire FR/AR",
        "",
        "Corpus BAM : loi 103-12, édition consolidée au 31 mars 2022. "
        "Les scores décrivent ce petit benchmark interne et ne valident pas le droit actuel.",
        "",
        f"Split : **{split}**. Les traductions d'un thème restent dans le même split. "
        "Les quatre directions linguistiques sont corrélées ; aucun intervalle "
        "d'indépendance artificiel n'est calculé.",
        "",
        scope_note,
        "",
        "| Méthode | Direction | Recall@5 | MRR@5 | Positifs acceptés | Négatifs refusés |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for report in reports:
        mode = report["metadata"]["mode"]
        dump_json(directory / f"{mode}.json", report)
        for row in report["aggregate"]:
            if row["direction"] == "macro_direction":
                continue

            def number(value):
                return "—" if value is None else f"{value:.3f}"

            values = [
                mode,
                row["direction"],
                number(row.get("recall_at_5")),
                number(row.get("mrr_at_5")),
                number(row["positive_answer_rate"]),
                number(row["negative_abstention_rate"]),
            ]
            lines.append("| " + " | ".join(values) + " |")
    metadata = reports[0]["metadata"]
    lines += [
        "",
        f"{metadata['n_cases']} couples question/langue-source, "
        f"{metadata['n_topic_groups']} thèmes, par méthode. "
        "Le rappel et MRR portent uniquement sur les questions annotées comme répondables.",
        "",
        "Les seuils d'abstention ont été choisis sur développement, puis conservés "
        "pour le test. L'abstention est une heuristique sur les passages retrouvés "
        "et la portée temporelle du corpus, pas un vérificateur de vérité.",
        "",
        "**Fidélité générative non évaluée par ce benchmark.** "
        "La validité d'un identifiant ou la présence d'une citation ne prouve pas "
        "qu'une paraphrase générée est justifiée. Les résultats ci-dessus "
        "n'impliquent aucune mesure de qualité de Qwen/Ollama.",
        "",
        "Les JSON conservent chaque question originale, son groupe, les articles attendus "
        "et retrouvés, les décisions d'abstention, la provenance et les latences. "
        "Ils ne contiennent aucun texte intégral ou extrait des PDF BAM.",
        "",
        "Les temps de recherche excluent le chargement du modèle/index et la génération. "
        "Les poids ONNX sont préparés localement ; le corpus bancaire ne quitte pas "
        "la machine pour être encodé.",
        "",
        "Les mesures ci-dessus concernent la recherche documentaire locale. "
        "Le statut des validations HTTP, Docker, OpenSearch et de génération "
        "est documenté séparément dans reports/VALIDATION.md.",
        "",
    ]
    dump_json(directory / "policy_used.json", policy)
    (directory / "RESULTATS.md").write_text("\n".join(lines), encoding="utf-8")


def make_parser():
    parser = argparse.ArgumentParser(
        description="Assistant documentaire bancaire FR/AR, édition 2022."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name in [
        "download",
        "ingest",
        "prepare-model",
        "ask",
        "evaluate",
        "calibrate",
        "index-opensearch",
        "serve",
    ]:
        item = sub.add_parser(name)
        item.add_argument("--data-dir", type=Path, default=Path("data"))
        if name in {"ask", "evaluate", "calibrate", "index-opensearch", "serve"}:
            item.add_argument("--encoder", choices=["none", "multilingual"], default="none")
            item.add_argument(
                "--preprocessing", choices=["raw", "normalized"], default="normalized"
            )
            item.add_argument("--backend", choices=["local", "opensearch"], default="local")
            item.add_argument(
                "--policy", type=Path, default=ROOT / "evaluation/abstention_policy.json"
            )
        if name == "ask":
            item.add_argument("question")
            item.add_argument("--source-language", choices=["fr", "ar"])
            item.add_argument("--mode", choices=["bm25", "semantic", "hybrid"], default="bm25")
            item.add_argument("--generator", choices=["extractive", "ollama"], default="extractive")
        if name in {"evaluate", "calibrate"}:
            item.add_argument("--questions", type=Path, default=ROOT / "evaluation/questions.json")
            item.add_argument("--top-k", type=int, choices=[5], default=5)
        if name == "evaluate":
            item.add_argument("--split", choices=["dev", "test"], default="dev")
            item.add_argument(
                "--modes", nargs="+", choices=["bm25", "semantic", "hybrid"], default=["bm25"]
            )
            item.add_argument("--output-dir", type=Path, default=Path("outputs/evaluation"))
            item.add_argument(
                "--analysis-status",
                choices=["descriptive_pilot", "exploratory_after_initial_test", ANALYSIS_STATUS],
                default="descriptive_pilot",
            )
            item.add_argument(
                "--evaluation-manifest",
                type=Path,
                help="Explicit frozen-policy evaluation of an audited, new-topic challenge.",
            )
        if name == "calibrate":
            item.add_argument(
                "--output", type=Path, default=ROOT / "evaluation/abstention_policy.json"
            )
        if name == "serve":
            item.add_argument("--host", default="127.0.0.1")
            item.add_argument("--port", type=int, default=8000)
            item.add_argument("--generator", choices=["extractive", "ollama"], default="extractive")
    return parser


def main(argv=None) -> int:
    parser = make_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "download":
            result = download_sources(args.data_dir)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif args.command == "ingest":
            articles = ingest_sources(args.data_dir)
            print(f"{len(articles)} articles validés dans {args.data_dir / 'processed'}.")
        elif args.command == "prepare-model":
            from .embeddings import MultilingualEncoder

            model = MultilingualEncoder(args.data_dir / "models", allow_download=True)
            print(json.dumps(model.metadata, ensure_ascii=False, indent=2))
        else:
            settings = replace(
                Settings.from_env(),
                data_dir=args.data_dir,
                encoder=args.encoder,
                preprocessing=args.preprocessing,
                backend=args.backend,
                policy_path=args.policy,
            )
            if args.command == "serve":
                import uvicorn

                from .api import create_app

                uvicorn.run(
                    create_app(replace(settings, generator=args.generator)),
                    host=args.host,
                    port=args.port,
                )
                return 0
            retriever = build_retriever(settings)
            if args.command == "index-opensearch":
                if args.backend != "opensearch":
                    raise ValueError("Préciser --backend opensearch pour une indexation explicite.")
                print(json.dumps(retriever.index(), ensure_ascii=False, indent=2))
            elif args.command == "calibrate":
                data = calibrate(retriever, args.questions, args.output, args.top_k)
                print(
                    json.dumps(
                        {"policy": data["policy"], "output": str(args.output)},
                        ensure_ascii=False,
                        indent=2,
                    )
                )
            elif args.command == "evaluate":
                policy = (
                    json.loads(args.policy.read_text(encoding="utf-8"))
                    if args.policy.exists()
                    else {}
                )
                transfer = None
                if args.evaluation_manifest is not None:
                    if args.analysis_status != ANALYSIS_STATUS:
                        raise ValueError("Un manifeste exige --analysis-status " + ANALYSIS_STATUS)
                    transfer = validate_manifest(
                        args.evaluation_manifest,
                        ROOT,
                        args.questions,
                        args.policy,
                        retriever,
                        signature(retriever),
                        args.modes,
                        args.top_k,
                        args.split,
                    )
                    if args.output_dir.exists() and any(args.output_dir.iterdir()):
                        raise ValueError("Le dossier du nouveau challenge doit être vide.")
                elif args.analysis_status == ANALYSIS_STATUS:
                    raise ValueError(
                        "Ce statut exige un manifeste de questions/code audités et gelés."
                    )
                elif args.split == "test" and (
                    policy.get("retriever_signature") != signature(retriever)
                    or policy.get("benchmark_sha256") != benchmark_hash(args.questions)
                ):
                    raise ValueError(
                        "Calibrer sur dev avec le même index et benchmark avant le test."
                    )
                service = AnswerService(retriever, AbstentionPolicy.load(args.policy))
                reports = [
                    evaluate_retrieval(
                        retriever,
                        load_cases(args.questions, args.split),
                        mode,
                        args.top_k,
                        decide_answer=service.accepts,
                    )
                    for mode in args.modes
                ]
                for report in reports:
                    report["metadata"]["analysis_status"] = args.analysis_status
                    report["metadata"]["policy"] = asdict(service.policy)
                    if transfer is not None:
                        report["metadata"]["evaluation_transfer"] = transfer
                        report["metadata"]["protocol_version"] = "bam-10312-new-topics-v2"
                    report["metadata"]["policy_status"] = (
                        "development_calibrated_on_original_benchmark"
                        if transfer is not None
                        else (
                            "development_calibrated"
                            if policy.get("retriever_signature") == signature(retriever)
                            else "illustrative_defaults_or_unmatched_policy"
                        )
                    )
                write_results(reports, args.output_dir, args.split, policy)
                print(args.output_dir / "RESULTATS.md")
            else:
                result = build_service(settings, retriever).ask(
                    args.question,
                    source_language=args.source_language,
                    mode=args.mode,
                    generator=args.generator,
                )
                print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, RuntimeError, OSError, ImportError) as error:
        parser.exit(2, f"Erreur : {error}\n")
    return 0
