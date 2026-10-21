"""Explicit corpus preparation, documentary queries and reproducible diagnostics."""

import argparse
import json
from pathlib import Path

from rag_reglementation_maroc.runtime import Settings, build_service

from .corpus import download, ingest
from .service import AssistantService


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Assistant documentaire V3 — réclamations et médiation"
    )
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser(
        "prepare-domain", help="Télécharger et vérifier le recueil, puis extraire les 24 articles"
    )
    ask = sub.add_parser("ask")
    ask.add_argument("question")
    ask.add_argument("--source-language", choices=["fr", "ar"])
    ask.add_argument("--encoder", choices=["none", "multilingual"], default="none")
    ask.add_argument("--mode", choices=["bm25", "semantic", "hybrid"], default="bm25")
    evaluate = sub.add_parser("evaluate-development")
    evaluate.add_argument(
        "--cases", type=Path, default=Path("evaluation/assistant_v3_development.json")
    )
    evaluate.add_argument("--output", type=Path, required=True)
    evaluate.add_argument("--encoder", choices=["none", "multilingual"], default="none")
    evaluate.add_argument("--mode", choices=["bm25", "semantic", "hybrid"], default="bm25")
    freeze = sub.add_parser("freeze-test")
    freeze.add_argument("--cases", type=Path, required=True)
    freeze.add_argument("--manifest", type=Path, required=True)
    freeze.add_argument("--encoder", choices=["none", "multilingual"], default="multilingual")
    freeze.add_argument("--mode", choices=["bm25", "semantic", "hybrid"], default="semantic")
    reserved = sub.add_parser("evaluate-test")
    reserved.add_argument("--cases", type=Path, required=True)
    reserved.add_argument("--manifest", type=Path, required=True)
    reserved.add_argument("--output", type=Path, required=True)
    reserved.add_argument("--private-output", type=Path, required=True)
    reserved.add_argument("--encoder", choices=["none", "multilingual"], default="multilingual")
    reserved.add_argument("--mode", choices=["bm25", "semantic", "hybrid"], default="semantic")
    review = sub.add_parser("import-review")
    review.add_argument("--results", type=Path, required=True)
    review.add_argument("--review", type=Path, required=True)
    review.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "prepare-domain":
        download(args.data_dir)
        quality = ingest(args.data_dir)
        print(
            json.dumps(
                {k: v for k, v in quality.items() if k != "article_hashes"},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if args.command == "import-review":
        from .review import import_review

        print(
            json.dumps(
                import_review(args.results, args.review, args.output), ensure_ascii=False, indent=2
            )
        )
        return 0
    settings = Settings(data_dir=args.data_dir, encoder=args.encoder)
    service = AssistantService(build_service(settings), args.data_dir)
    if args.command == "freeze-test":
        from .review import freeze_reserved

        print(
            json.dumps(
                freeze_reserved(service, args.cases, args.manifest, args.mode),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if args.command == "evaluate-test":
        from .review import evaluate_reserved

        report = evaluate_reserved(
            service, args.cases, args.manifest, args.output, args.private_output, args.mode
        )
        print(
            json.dumps(
                {key: value for key, value in report.items() if key != "rows"},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if args.command == "ask":
        print(
            json.dumps(
                service.ask(args.question, source_language=args.source_language, mode=args.mode),
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        from .evaluation import evaluate_development

        report = evaluate_development(service, args.cases, args.output, args.mode)
        print(json.dumps(report["metrics"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
