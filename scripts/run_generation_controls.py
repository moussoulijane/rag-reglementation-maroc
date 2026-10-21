"""One-shot provider controls on invented facts, separate from the failed V2 lot."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

import httpx

from rag_reglementation_maroc.answering import GeneratedAnswer

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "reports/generation-development-controls/protocol.json"
PUBLIC = ROOT / "reports/generation-development-controls/results.json"
PRIVATE = ROOT / "outputs/generation-development-controls/raw.json"


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run():
    if PUBLIC.exists() or PRIVATE.exists():
        raise ValueError("Controls already executed; no overwrite or retry permitted.")
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    for name, digest in protocol["unchanged_artifacts_sha256"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Frozen artifact changed: {name}")
    state = {
        "started_at_utc": datetime.now(UTC).isoformat(),
        "protocol_sha256": hashlib.sha256(PROTOCOL.read_bytes()).hexdigest(),
        "controls": [],
    }
    with httpx.Client(trust_env=False, timeout=protocol["timeout_seconds"]) as client:
        loaded = client.get(protocol["base_url"] + "/api/ps").json()["models"]
        if not any(item["name"] == protocol["model"]["name"] for item in loaded):
            with httpx.Client(trust_env=False, timeout=protocol["preload_timeout_seconds"]) as warm:
                response = warm.post(
                    protocol["base_url"] + "/api/generate",
                    json={
                        "model": protocol["model"]["name"],
                        "stream": False,
                        "keep_alive": protocol["keep_alive"],
                        "options": {"num_ctx": protocol["options"]["num_ctx"]},
                    },
                )
                response.raise_for_status()
                state["preload"] = response.json()
        write(PRIVATE, state)
        summaries = []
        for case in protocol["controls"]:
            started = perf_counter()
            row = {"id": case["id"], "error": None}
            try:
                response = client.post(
                    protocol["base_url"] + case["endpoint"], json=case["payload"]
                )
                response.raise_for_status()
                provider = response.json()
                content = (
                    provider["response"]
                    if case["endpoint"] == "/api/generate"
                    else provider["message"]["content"]
                )
                row["provider"] = provider
                row["content"] = content
                try:
                    parsed = json.loads(content)
                except ValueError:
                    parsed = None
                row["parsed"] = parsed
                valid = False
                if parsed is not None:
                    if case["response_contract"] == "original":
                        try:
                            GeneratedAnswer.model_validate(parsed)
                            valid = True
                        except ValueError:
                            pass
                    elif case["response_contract"] == "minimal":
                        valid = isinstance(parsed, dict) and all(
                            isinstance(parsed.get(key), str)
                            for key in ("answer", "citation_id", "quote")
                        )
                    else:
                        valid = isinstance(parsed, dict)
                row["schema_valid"] = valid
                row["expected_code_present"] = case["expected_code"] in content
                row["abstain"] = parsed.get("abstain") if isinstance(parsed, dict) else None
            except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
                row["error"] = {"type": type(error).__name__, "message": str(error)}
            row["latency_ms"] = (perf_counter() - started) * 1000
            state["controls"].append(row)
            write(PRIVATE, state)
            summary = {
                key: row.get(key)
                for key in ("id", "schema_valid", "expected_code_present", "abstain", "latency_ms")
            }
            summary["error"] = row["error"]["type"] if row["error"] else None
            summaries.append(summary)
            write(
                PUBLIC,
                {
                    "protocol_sha256": state["protocol_sha256"],
                    "scope": protocol["purpose"],
                    "controls": summaries,
                    "no_aggregate_quality_metric": True,
                },
            )
            print(json.dumps(summary), flush=True)
    for name, digest in protocol["unchanged_artifacts_sha256"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Artifact changed during controls: {name}")
    state["finished_at_utc"] = datetime.now(UTC).isoformat()
    write(PRIVATE, state)


if __name__ == "__main__":
    run()
