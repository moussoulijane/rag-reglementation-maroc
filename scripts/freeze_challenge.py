"""Freeze a reviewed internal challenge before running retrieval; never overwrite a freeze."""

import argparse
import json
from pathlib import Path

from rag_reglementation_maroc.evaluation_manifest import create_manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=Path, default=Path("evaluation/challenge_v2.json"))
    parser.add_argument("--origin", type=Path, default=Path("evaluation/questions.json"))
    parser.add_argument("--policy", type=Path, default=Path("evaluation/abstention_policy.json"))
    parser.add_argument("--audit", type=Path, default=Path("evaluation/challenge_v2_audit.json"))
    parser.add_argument(
        "--output", type=Path, default=Path("evaluation/challenge_v2_manifest.json")
    )
    parser.add_argument("--protocol", type=Path, default=Path("docs/CHALLENGE_V2.md"))
    args = parser.parse_args()
    manifest = create_manifest(
        Path.cwd(), args.questions, args.origin, args.policy, args.audit, args.protocol
    )
    with args.output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(args.output)


if __name__ == "__main__":
    main()
