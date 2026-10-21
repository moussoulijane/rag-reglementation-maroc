"""Smoke-report plumbing tested with local fixtures, never a real model call."""

import importlib.util
import json
from pathlib import Path

import httpx


def load_script():
    path = Path(__file__).resolve().parents[1] / "scripts/run_ollama_smoke.py"
    spec = importlib.util.spec_from_file_location("run_ollama_smoke_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_first_run_archives_are_created_once_without_overwriting(tmp_path):
    module = load_script()
    for folder, filename in (("reports", "ollama_smoke"), ("outputs", "ollama_smoke_raw")):
        target = tmp_path / folder / f"{filename}.json"
        target.parent.mkdir()
        target.write_text('{"first_run":true}', encoding="utf-8")
    module.preserve_first_run(tmp_path)
    for folder, filename in (("reports", "ollama_smoke"), ("outputs", "ollama_smoke_raw")):
        original = tmp_path / folder / f"{filename}.json"
        archive = tmp_path / folder / f"{filename}_v1.json"
        assert archive.read_bytes() == original.read_bytes()
        original.write_text('{"second_run":true}', encoding="utf-8")
    module.preserve_first_run(tmp_path)
    for archive in tmp_path.glob("*/*_v1.json"):
        assert json.loads(archive.read_text())["first_run"] is True


def test_mocked_main_keeps_provider_output_and_statistics_out_of_public_report(
    tmp_path,
    monkeypatch,
    capsys,
):
    module = load_script()
    private_quote = "SYNTHETIC PRIVATE SOURCE QUOTE"

    class Model:
        def reset_diagnostics(self):
            self.last_stats = {}
            self.last_generation = None

    class Service:
        policy_status = "development_calibrated"
        ollama = Model()

        def ask(self, *args, **kwargs):
            self.ollama.last_stats = {"prompt_eval_count": 1234, "done_reason": "stop"}
            self.ollama.last_generation = {
                "raw_content": private_quote,
                "parsed": {"claims": [private_quote]},
                "schema_valid": True,
            }
            return {
                "status": "evidence_found",
                "reason": None,
                "answer": private_quote,
                "citations": [{"article_id": "34", "quote": private_quote}],
                "latency_ms": 5.0,
            }

    class Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url):
            return httpx.Response(
                200,
                request=httpx.Request("GET", url),
                json={
                    "models": [{"name": "qwen2.5:7b", "digest": "synthetic-model-digest"}],
                },
            )

    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "build_service", lambda settings: Service())
    monkeypatch.setattr(module.httpx, "Client", Client)
    module.main()
    public_text = (tmp_path / "reports/ollama_smoke.json").read_text(encoding="utf-8")
    private_text = (tmp_path / "outputs/ollama_smoke_raw.json").read_text(encoding="utf-8")
    assert private_quote not in public_text and private_quote not in capsys.readouterr().out
    assert "prompt_eval_count" not in public_text and "provider_generation" not in public_text
    records = json.loads(private_text)
    assert len(records) == 4 and private_quote in private_text
    assert records[0]["provider_stats"]["prompt_eval_count"] == 1234
    assert records[0]["provider_generation"]["schema_valid"] is True
    public = json.loads(public_text)
    assert public["source_text_redistributed"] is False
    assert all(example["citation_article_ids"] == ["34"] for example in public["examples"])


def test_targeted_only_retains_both_generic_failures_and_their_diagnostics(tmp_path):
    module = load_script()
    previous = []
    for example in module.EXAMPLES[:2]:
        previous.append(
            {
                "question": example["question"],
                "result": {"status": "abstained", "reason": "model_found_no_supported_answer"},
                "provider_stats": {"done_reason": "stop", "eval_count": 11},
                "provider_generation": {"parsed": {"abstain": True, "claims": []}},
            }
        )
    output = tmp_path / "outputs"
    output.mkdir()
    (output / "ollama_smoke_raw.json").write_text(json.dumps(previous), encoding="utf-8")
    retained = module.retained_generic_rows(tmp_path)
    assert len(retained) == 2
    for original, row in zip(previous, retained, strict=True):
        assert row["result"] == original["result"]
        assert row["provider_stats"] == original["provider_stats"]
        assert row["provider_generation"] == original["provider_generation"]
        assert row["case_type"] == "generic"
        assert row["execution_stage"] == "retained_prior_generic"
