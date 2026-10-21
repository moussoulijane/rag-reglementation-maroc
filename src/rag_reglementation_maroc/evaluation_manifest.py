"""Explicit, audited transfer of a frozen policy to new internal evaluation topics."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from .evaluation import load_cases
from .text import normalize

ANALYSIS_STATUS = "prospective_internal_challenge"
DIRECTIONS = {("fr", "fr"), ("ar", "ar"), ("fr", "ar"), ("ar", "fr")}


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cases_sha256(path: Path) -> str:
    return hashlib.sha256(
        json.dumps(load_cases(path), sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _resource(root: Path, path: Path) -> dict:
    return {
        "path": path.resolve().relative_to(root.resolve()).as_posix(),
        "sha256": file_sha256(path),
    }


def _source_files(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): file_sha256(path)
        for path in sorted((root / "src/rag_reglementation_maroc").glob("*.py"))
    }


def check_new_topics(questions: Path, origin: Path) -> list[dict]:
    """Mechanical separation is necessary; semantic topic separation needs review."""
    cases = load_cases(questions)
    baseline = load_cases(origin)
    if not cases or any(case["split"] != "test" for case in cases):
        raise ValueError("A new-topic challenge must be nonempty and entirely test.")
    if not any(case["answerable"] for case in cases) or all(case["answerable"] for case in cases):
        raise ValueError("A new-topic challenge needs positives and negatives.")
    for key in ("id", "group_id"):
        if {case[key] for case in cases} & {case[key] for case in baseline}:
            raise ValueError(f"Challenge {key} overlaps the calibration/original test benchmark.")
    if {normalize(case["question"]) for case in cases} & {
        normalize(case["question"]) for case in baseline
    }:
        raise ValueError("A challenge question repeats an original benchmark question.")
    groups: dict[str, list[dict]] = {}
    for case in cases:
        groups.setdefault(case["group_id"], []).append(case)
    for rows in groups.values():
        if (
            len(rows) != 4
            or {(row["query_language"], row["source_language"]) for row in rows} != DIRECTIONS
        ):
            raise ValueError("Each challenge topic needs exactly the four language directions.")
        labels = {(row["answerable"], tuple(sorted(row["expected_article_ids"]))) for row in rows}
        if len(labels) != 1:
            raise ValueError("A challenge topic must share its answerability and article labels.")
        for language in ("fr", "ar"):
            formulations = {row["question"] for row in rows if row["query_language"] == language}
            if len(formulations) != 1:
                raise ValueError("A topic needs one formulation per query language.")
    return cases


def _check_calibration(policy: dict, origin: Path) -> None:
    if policy.get("status") != "development_calibrated":
        raise ValueError("An explicitly development-calibrated policy is required.")
    if policy.get("benchmark_sha256") != cases_sha256(origin):
        raise ValueError("The original calibration benchmark does not match the policy.")
    dev = load_cases(origin, "dev")
    if not dev or policy.get("development_groups") != sorted({case["group_id"] for case in dev}):
        raise ValueError("The policy development groups do not match the original benchmark.")


def _check_audit(audit: dict, questions: Path) -> None:
    if (
        audit.get("status") != "internal_audit_passed"
        or audit.get("questions_sha256") != file_sha256(questions)
        or audit.get("no_rankings_consulted") is not True
        or audit.get("semantic_topic_overlap_reviewed") is not True
    ):
        raise ValueError("A matching, completed internal annotation audit is required.")


def create_manifest(
    root: Path,
    questions: Path,
    origin: Path,
    policy_path: Path,
    audit_path: Path,
    protocol_path: Path,
) -> dict:
    cases = check_new_topics(questions, origin)
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    _check_calibration(policy, origin)
    _check_audit(audit, questions)
    modes = sorted({row["mode"] for row in policy.get("candidate_grid", [])})
    if not modes:
        raise ValueError("The policy must record which retrieval modes were calibrated.")
    return {
        "schema_version": 1,
        "evaluation_id": "bam-10312-new-topics-v2",
        "analysis_status": ANALYSIS_STATUS,
        "frozen_at_utc": datetime.now(UTC).isoformat(),
        "resources": {
            "questions": _resource(root, questions),
            "calibration_questions": _resource(root, origin),
            "policy": _resource(root, policy_path),
            "annotation_audit": _resource(root, audit_path),
            "evaluation_protocol": _resource(root, protocol_path),
        },
        "source_files_sha256": _source_files(root),
        "cases_sha256": cases_sha256(questions),
        "calibration_benchmark_sha256": cases_sha256(origin),
        "retriever_signature": policy["retriever_signature"],
        "modes": modes,
        "top_k": 5,
        "groups": sorted({case["group_id"] for case in cases}),
        "n_cases": len(cases),
        "policy_transfer": "Original development thresholds reused without recalibration.",
        "annotation_review": "Internal review without retrieval rankings; no external legal adjudication.",
        "limits": (
            "Local prospective record, not external preregistration or tamper-proof attestation. "
            "Mechanical disjointness cannot prove semantic novelty or annotation correctness. "
            "Translated directions are correlated. No generated faithfulness evaluation."
        ),
    }


def validate_manifest(
    manifest_path: Path,
    root: Path,
    questions: Path,
    policy_path: Path,
    retriever,
    retriever_signature: str,
    modes: list[str],
    top_k: int,
    split: str,
) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        manifest.get("schema_version") != 1
        or manifest.get("analysis_status") != ANALYSIS_STATUS
        or split != "test"
    ):
        raise ValueError("The frozen new-topic route requires its test-only manifest.")
    resources = {}
    for name in (
        "questions",
        "calibration_questions",
        "policy",
        "annotation_audit",
        "evaluation_protocol",
    ):
        entry = manifest["resources"][name]
        path = (root / entry["path"]).resolve()
        if not path.is_relative_to(root.resolve()) or file_sha256(path) != entry["sha256"]:
            raise ValueError(f"Frozen resource mismatch: {name}.")
        resources[name] = path
    if (
        resources["questions"] != questions.resolve()
        or resources["policy"] != policy_path.resolve()
    ):
        raise ValueError("CLI questions/policy must match the frozen manifest paths.")
    if manifest.get("source_files_sha256") != _source_files(root):
        raise ValueError("Source code changed since the new-topic evaluation was frozen.")
    cases = check_new_topics(questions, resources["calibration_questions"])
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    _check_calibration(policy, resources["calibration_questions"])
    _check_audit(json.loads(resources["annotation_audit"].read_text(encoding="utf-8")), questions)
    if (
        manifest.get("cases_sha256") != cases_sha256(questions)
        or manifest.get("calibration_benchmark_sha256")
        != cases_sha256(resources["calibration_questions"])
        or manifest.get("groups") != sorted({case["group_id"] for case in cases})
        or manifest.get("n_cases") != len(cases)
    ):
        raise ValueError("Challenge metadata changed since the freeze.")
    if retriever_signature != policy.get(
        "retriever_signature"
    ) or retriever_signature != manifest.get("retriever_signature"):
        raise ValueError("The current retriever must exactly match the frozen calibrated index.")
    calibrated_modes = {row["mode"] for row in policy.get("candidate_grid", [])}
    if (
        top_k != 5
        or manifest.get("top_k") != 5
        or set(manifest.get("modes", [])) != calibrated_modes
        or not modes
        or not set(modes) <= calibrated_modes
    ):
        raise ValueError("Only calibrated modes with top_k=5 may be transferred.")
    articles = getattr(retriever, "articles", {})
    values = articles.values() if isinstance(articles, dict) else articles
    available = {
        (article.article_id, article.language)
        for article in values
        if article.version_date == policy["policy"]["version_date"]
    }
    for case in cases:
        if any(
            (article_id, case["source_language"]) not in available
            for article_id in case["expected_article_ids"]
        ):
            raise ValueError("A challenge annotation refers to a missing article/language/edition.")
    return {
        "analysis_status": ANALYSIS_STATUS,
        "evaluation_id": manifest["evaluation_id"],
        "manifest_sha256": file_sha256(manifest_path),
        "frozen_at_utc": manifest["frozen_at_utc"],
        "challenge_file_sha256": file_sha256(questions),
        "calibration_benchmark_sha256": policy["benchmark_sha256"],
        "policy_file_sha256": file_sha256(policy_path),
        "annotation_audit_sha256": file_sha256(resources["annotation_audit"]),
        "evaluation_protocol_sha256": file_sha256(resources["evaluation_protocol"]),
        "policy_transfer": manifest["policy_transfer"],
        "annotation_review": manifest["annotation_review"],
        "limits": manifest["limits"],
    }
