"""A new-topic evaluation must not silently relax calibration and freeze checks."""

import json

import pytest

from rag_reglementation_maroc import cli
from rag_reglementation_maroc.evaluation_manifest import (
    ANALYSIS_STATUS,
    create_manifest,
    file_sha256,
    validate_manifest,
)


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def quartet(group, french, arabic, expected):
    return [
        {
            "id": f"{group}-{query}-{source}",
            "group_id": group,
            "split": "test",
            "question": french if query == "fr" else arabic,
            "query_language": query,
            "source_language": source,
            "answerable": bool(expected),
            "expected_article_ids": expected,
        }
        for query, source in [("fr", "fr"), ("ar", "ar"), ("fr", "ar"), ("ar", "fr")]
    ]


@pytest.fixture
def frozen(tmp_path, retriever):
    source = tmp_path / "src/rag_reglementation_maroc"
    source.mkdir(parents=True)
    (source / "__init__.py").write_text("VERSION = 1\n", encoding="utf-8")
    origin = tmp_path / "origin.json"
    original = []
    for split, group, question, expected in [
        ("dev", "old-positive", "agrément banques", ["34"]),
        ("dev", "old-negative", "xyzzqvunrelated", []),
        ("test", "old-test-positive", "réclamations écrites", ["157"]),
        ("test", "old-test-negative", "xyzzqunknown", []),
    ]:
        original.append(
            {
                "id": group,
                "group_id": group,
                "split": split,
                "question": question,
                "query_language": "fr",
                "source_language": "fr",
                "answerable": bool(expected),
                "expected_article_ids": expected,
            }
        )
    write_json(origin, {"cases": original})
    policy = tmp_path / "policy.json"
    cli.calibrate(retriever, origin, policy)
    questions = tmp_path / "new.json"
    cases = quartet(
        "new-agency",
        "Qui faut-il prévenir avant de fermer un point de service ?",
        "من يجب إخباره قبل إغلاق الوكالة؟",
        ["155"],
    ) + quartet(
        "new-unsupported",
        "Quel prix une banque facture-t-elle pour un service premium ?",
        "ما ثمن خدمة مميزة لدى بنك تجاري؟",
        [],
    )
    write_json(questions, {"cases": cases})
    audit = tmp_path / "audit.json"
    manifest_path = tmp_path / "manifest.json"
    protocol = tmp_path / "protocol.md"
    protocol.write_text(
        "Recall@5 and refusals in all four directions. No tuning.", encoding="utf-8"
    )

    def refreeze():
        write_json(
            audit,
            {
                "status": "internal_audit_passed",
                "questions_sha256": file_sha256(questions),
                "no_rankings_consulted": True,
                "semantic_topic_overlap_reviewed": True,
            },
        )
        manifest = create_manifest(tmp_path, questions, origin, policy, audit, protocol)
        write_json(manifest_path, manifest)
        return manifest

    refreeze()
    return {
        "root": tmp_path,
        "origin": origin,
        "questions": questions,
        "policy": policy,
        "audit": audit,
        "protocol": protocol,
        "manifest": manifest_path,
        "source": source / "__init__.py",
        "refreeze": refreeze,
        "retriever": retriever,
    }


def validate(frozen, **changes):
    arguments = {
        "manifest_path": frozen["manifest"],
        "root": frozen["root"],
        "questions": frozen["questions"],
        "policy_path": frozen["policy"],
        "retriever": frozen["retriever"],
        "retriever_signature": cli.signature(frozen["retriever"]),
        "modes": ["bm25"],
        "top_k": 5,
        "split": "test",
    }
    arguments.update(changes)
    return validate_manifest(**arguments)


def test_transfers_frozen_policy_without_recalibrating(frozen, monkeypatch):
    before = frozen["policy"].read_bytes()
    monkeypatch.setattr(cli, "calibrate", lambda *a: pytest.fail("No new calibration allowed."))
    result = validate(frozen)
    assert result["analysis_status"] == ANALYSIS_STATUS
    assert result["calibration_benchmark_sha256"] == cli.benchmark_hash(frozen["origin"])
    assert result["calibration_benchmark_sha256"] != cli.benchmark_hash(frozen["questions"])
    assert frozen["policy"].read_bytes() == before


@pytest.mark.parametrize(
    "resource", ["questions", "origin", "policy", "audit", "source", "protocol"]
)
def test_refuses_any_changed_frozen_resource(frozen, resource):
    with frozen[resource].open("a", encoding="utf-8") as stream:
        stream.write("\n")
    with pytest.raises(ValueError, match="mismatch|changed"):
        validate(frozen)


@pytest.mark.parametrize(
    "changes",
    [
        {"retriever_signature": "another-index"},
        {"modes": ["semantic"]},
        {"top_k": 10},
        {"split": "dev"},
    ],
)
def test_refuses_unmatched_index_uncalibrated_modes_or_scope(frozen, changes):
    with pytest.raises(ValueError):
        validate(frozen, **changes)


@pytest.mark.parametrize("mutation", ["group", "question", "quartet", "labels", "dev"])
def test_refuses_old_topics_or_inconsistent_new_cases(frozen, mutation):
    content = json.loads(frozen["questions"].read_text(encoding="utf-8"))
    rows = content["cases"]
    if mutation == "group":
        for row in rows[:4]:
            row["group_id"] = "old-test-positive"
    elif mutation == "question":
        for row in rows[:4]:
            if row["query_language"] == "fr":
                row["question"] = "RÉCLAMATIONS écrites"
    elif mutation == "quartet":
        rows.pop()
    elif mutation == "labels":
        rows[0]["expected_article_ids"] = ["34"]
    else:
        for row in rows:
            row["split"] = "dev"
    write_json(frozen["questions"], content)
    with pytest.raises(ValueError):
        frozen["refreeze"]()


def test_refuses_missing_review_and_absent_article_annotations(frozen):
    audit = json.loads(frozen["audit"].read_text(encoding="utf-8"))
    audit["no_rankings_consulted"] = False
    write_json(frozen["audit"], audit)
    with pytest.raises(ValueError, match="audit"):
        create_manifest(
            frozen["root"],
            frozen["questions"],
            frozen["origin"],
            frozen["policy"],
            frozen["audit"],
            frozen["protocol"],
        )
    content = json.loads(frozen["questions"].read_text(encoding="utf-8"))
    for row in content["cases"][:4]:
        row["expected_article_ids"] = ["999"]
    write_json(frozen["questions"], content)
    frozen["refreeze"]()
    with pytest.raises(ValueError, match="missing article"):
        validate(frozen)


def test_cannot_relabel_an_unmatched_original_as_calibrated(frozen):
    origin = json.loads(frozen["origin"].read_text(encoding="utf-8"))
    origin["cases"][0]["question"] = "Another development question"
    write_json(frozen["origin"], origin)
    with pytest.raises(ValueError, match="original calibration benchmark"):
        frozen["refreeze"]()


def test_cli_requires_explicit_manifest_and_preserves_results(frozen, monkeypatch):
    monkeypatch.setattr(cli, "ROOT", frozen["root"])
    monkeypatch.setattr(cli, "build_retriever", lambda settings: frozen["retriever"])
    output = frozen["root"] / "results"
    command = [
        "evaluate",
        "--split",
        "test",
        "--questions",
        str(frozen["questions"]),
        "--policy",
        str(frozen["policy"]),
        "--output-dir",
        str(output),
        "--analysis-status",
        ANALYSIS_STATUS,
    ]
    with pytest.raises(SystemExit) as error:
        cli.main(command)
    assert error.value.code == 2
    assert not output.exists()
    command += ["--evaluation-manifest", str(frozen["manifest"])]
    assert cli.main(command) == 0
    result_file = output / "bm25.json"
    before = result_file.read_bytes()
    report = json.loads(before)
    assert report["metadata"]["evaluation_transfer"]["manifest_sha256"]
    assert report["metadata"]["protocol_version"] == "bam-10312-new-topics-v2"
    with pytest.raises(SystemExit):
        cli.main(command)
    assert result_file.read_bytes() == before
