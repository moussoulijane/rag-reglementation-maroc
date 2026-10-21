"""Le test doit utiliser la politique et le benchmark effectivement calibrés."""

import json

import pytest

from rag_reglementation_maroc import cli
from rag_reglementation_maroc.runtime import Settings, build_service


def cases_file(path):
    cases = []
    for split, topic, question, expected in [
        ("dev", "dev-positive", "agrément banques", ["34"]),
        ("dev", "dev-negative", "xyzzqvunrelated", []),
        ("test", "test-positive", "fermeture agence", ["155"]),
        ("test", "test-negative", "xyzzqunknown", []),
    ]:
        cases.append(
            {
                "id": topic,
                "group_id": topic,
                "split": split,
                "question": question,
                "query_language": "fr",
                "source_language": "fr",
                "answerable": bool(expected),
                "expected_article_ids": expected,
            }
        )
    path.write_text(json.dumps({"cases": cases}), encoding="utf-8")
    return path


def test_cli_refuses_unmatched_test_policy_then_writes_real_measurements(
    tmp_path,
    monkeypatch,
    retriever,
):
    questions = cases_file(tmp_path / "questions.json")
    policy = tmp_path / "policy.json"
    output = tmp_path / "results"
    monkeypatch.setattr(cli, "build_retriever", lambda settings: retriever)
    command = [
        "evaluate",
        "--split",
        "test",
        "--questions",
        str(questions),
        "--policy",
        str(policy),
        "--output-dir",
        str(output),
    ]
    with pytest.raises(SystemExit) as error:
        cli.main(command)
    assert error.value.code == 2
    assert not output.exists()
    calibrated = cli.calibrate(retriever, questions, policy)
    assert set(calibrated["development_groups"]) == {"dev-positive", "dev-negative"}
    assert cli.main(command) == 0
    report = json.loads((output / "bm25.json").read_text(encoding="utf-8"))
    assert report["metadata"]["splits"] == ["test"]
    assert report["metadata"]["faithfulness_evaluated"] is False
    assert report["metadata"]["n_cases"] == 2
    assert (output / "RESULTATS.md").exists()
    content = json.loads(questions.read_text(encoding="utf-8"))
    content["cases"][-1]["question"] = "changed benchmark"
    questions.write_text(json.dumps(content), encoding="utf-8")
    with pytest.raises(SystemExit):
        cli.main(command)


def test_runtime_does_not_reuse_policy_from_another_index(tmp_path, retriever):
    path = tmp_path / "policy.json"
    path.write_text(
        json.dumps(
            {
                "retriever_signature": "different",
                "policy": {"lexical_threshold": 1.0},
            }
        ),
        encoding="utf-8",
    )
    service = build_service(Settings(policy_path=path), retriever)
    assert service.policy_status == "uncalibrated_for_this_index"
    assert service.policy.lexical_threshold == 0.25
