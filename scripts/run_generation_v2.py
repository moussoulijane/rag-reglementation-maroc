"""Run the frozen generation-v2 protocol with a separately timed cold preload.

No search configuration, question or threshold is selected from the outcomes.
Source passages and provider responses are written only below ignored outputs/.
"""

import hashlib
import json
import subprocess
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

import httpx

from rag_reglementation_maroc.answering import OllamaClient, citation
from rag_reglementation_maroc.runtime import Settings, build_service

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "reports/generation-v2/protocol.json"
PUBLIC = ROOT / "reports/generation-v2/results.json"
PRIVATE = ROOT / "outputs/generation-v2/raw.json"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def resources():
    command = (
        "$os=Get-CimInstance Win32_OperatingSystem; "
        "$p=@(Get-Process | Where-Object {$_.ProcessName -match 'docker|vmmem|ollama'} "
        "| ForEach-Object {[pscustomobject]@{name=$_.ProcessName;"
        "working_set_mb=[math]::Round($_.WorkingSet64/1MB,1)}}); "
        "[pscustomobject]@{free_ram_mb=[math]::Round($os.FreePhysicalMemory/1024,1);"
        "processes=$p} | ConvertTo-Json -Depth 4"
    )
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return json.loads(result.stdout)


def public_case(row):
    result = row["result"]
    error = row.get("provider_error") or {}
    return {
        "id": row["id"],
        "case_type": row["case_type"],
        "language": row["language"],
        "mode": row["mode"],
        "question": row["question"],
        "expected_article_ids": row["expected_article_ids"],
        "retrieved_article_ids": [hit["article_id"] for hit in row["retrieval_hits"]],
        "context_article_ids": sorted({hit["article_id"] for hit in row["context"]}),
        "status": result["status"],
        "reason": result["reason"],
        "citation_article_ids": [item["article_id"] for item in result["citations"]],
        "citation_count": len(result["citations"]),
        "exact_original_citations": row["exact_original_citations"],
        "latency_ms": result["latency_ms"],
        "provider_error": {
            "stage": error.get("stage"),
            "exception": error.get("exception"),
            "http_status": error.get("http_status"),
        }
        if error
        else None,
        "manual_review": "pending_internal_review" if result["citations"] else "no_accepted_claim",
    }


def check_history(protocol):
    for name, expected in protocol["historical_sha256"].items():
        if sha256(ROOT / name) != expected:
            raise ValueError(f"Historical file changed: {name}")


def hit_record(hit):
    return {
        "chunk_id": hit.chunk.id,
        "article_id": hit.article.article_id,
        "source_id": hit.article.source_id,
        "char_start": hit.chunk.char_start,
        "char_end": hit.chunk.char_end,
        "text": hit.chunk.text,
    }


def run():
    if PUBLIC.exists() or PRIVATE.exists():
        raise ValueError("This fixed batch already has results; refuse to overwrite or retry.")
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    conditions = protocol["conditions"]
    check_history(protocol)
    if sha256(ROOT / conditions["policy_path"]) != conditions["policy_sha256"]:
        raise ValueError("The policy changed after the protocol was fixed.")
    machine = resources()
    if any(
        "docker" in p["name"].lower() or "vmmem" in p["name"].lower() for p in machine["processes"]
    ):
        raise ValueError("Docker/vmmem is active; do not run concurrent inference.")
    settings = Settings(
        data_dir=ROOT / "data",
        encoder=conditions["encoder"],
        preprocessing=conditions["preprocessing"],
        backend=conditions["backend"],
        policy_path=ROOT / conditions["policy_path"],
    )
    service = build_service(settings)
    if service.policy_status != "development_calibrated":
        raise ValueError("The unchanged policy must match this exact index.")
    service.ollama = OllamaClient(
        settings.ollama_url,
        protocol["model"]["name"],
        timeout=conditions["inference_timeout_seconds"],
        options=conditions["generation_options"],
        keep_alive=conditions["keep_alive"],
    )
    with httpx.Client(trust_env=False, timeout=10) as client:
        installed = client.get(settings.ollama_url + "/api/tags").json()["models"]
        selected = next(model for model in installed if model["name"] == protocol["model"]["name"])
        if selected["digest"] != protocol["model"]["digest"]:
            raise ValueError("The installed model differs from the fixed protocol.")
    state = {
        "protocol_sha256": sha256(PROTOCOL),
        "started_at_utc": datetime.now(UTC).isoformat(),
        "machine_before": machine,
        "preload": None,
        "cases": [],
    }
    write_json(PRIVATE, state)
    print(json.dumps({"stage": "preload_started", "time": state["started_at_utc"]}), flush=True)
    started = perf_counter()
    try:
        with httpx.Client(trust_env=False, timeout=conditions["preload_timeout_seconds"]) as client:
            response = client.post(
                settings.ollama_url + "/api/generate",
                json={
                    "model": protocol["model"]["name"],
                    "stream": False,
                    "keep_alive": conditions["keep_alive"],
                    "options": {"num_ctx": conditions["generation_options"]["num_ctx"]},
                },
            )
            response.raise_for_status()
            provider = response.json()
            loaded = client.get(settings.ollama_url + "/api/ps").json()
        if not any(model["name"] == protocol["model"]["name"] for model in loaded["models"]):
            raise RuntimeError("Preload returned without the selected model being resident.")
        state["preload"] = {
            "status": "loaded",
            "wall_ms": (perf_counter() - started) * 1000,
            "provider": provider,
            "resident_models": loaded,
        }
    except (httpx.HTTPError, ValueError, RuntimeError) as error:
        state["preload"] = {
            "status": "failed",
            "wall_ms": (perf_counter() - started) * 1000,
            "exception": type(error).__name__,
            "message": str(error),
        }
        write_json(PRIVATE, state)
        write_json(
            PUBLIC,
            {
                "scope": protocol["scope"],
                "protocol_sha256": state["protocol_sha256"],
                "preload": {
                    key: value for key, value in state["preload"].items() if key != "message"
                },
                "cases": [],
                "conclusion": "Preload failed; no case was attempted.",
            },
        )
        raise
    write_json(PRIVATE, state)
    print(
        json.dumps({"stage": "preload_completed", "wall_ms": state["preload"]["wall_ms"]}),
        flush=True,
    )
    for case in protocol["cases"]:
        hits = service.retriever.search(
            case["question"],
            language=case["language"],
            mode=case["mode"],
            top_k=conditions["top_k"],
        )
        context = service.expand_evidence(hits)
        service.ollama.reset_diagnostics()
        result = service.ask(
            case["question"],
            source_language=case["language"],
            mode=case["mode"],
            top_k=conditions["top_k"],
            generator="ollama",
        )
        allowed = {hit.chunk.id: hit for hit in context}
        exact = None
        if result["citations"]:
            exact = all(
                item["chunk_id"] in allowed
                and item["quote"] in allowed[item["chunk_id"]].chunk.text
                and citation(allowed[item["chunk_id"]], item["quote"])["quote"] == item["quote"]
                for item in result["citations"]
            )
        row = {
            **case,
            "result": result,
            "retrieval_hits": [hit_record(hit) for hit in hits],
            "context": [hit_record(hit) for hit in context],
            "exact_original_citations": exact,
            "provider_stats": deepcopy(service.ollama.last_stats),
            "provider_generation": deepcopy(service.ollama.last_generation),
            "provider_error": deepcopy(service.ollama.last_error),
        }
        state["cases"].append(row)
        write_json(PRIVATE, state)
        summary = {
            "scope": protocol["scope"],
            "protocol_sha256": state["protocol_sha256"],
            "created_at_utc": datetime.now(UTC).isoformat(),
            "preload": {
                "status": state["preload"]["status"],
                "wall_ms": state["preload"]["wall_ms"],
                "excluded_from_case_latencies": True,
            },
            "model": protocol["model"],
            "policy_status": service.policy_status,
            "cases": [public_case(item) for item in state["cases"]],
            "human_review_scope": "Internal evidence check only; not independent legal annotation.",
            "source_text_redistributed": False,
            "no_aggregate_performance_rate": True,
        }
        write_json(PUBLIC, summary)
        print(json.dumps(public_case(row), ensure_ascii=False), flush=True)
    check_history(protocol)
    state["machine_after"] = resources()
    state["finished_at_utc"] = datetime.now(UTC).isoformat()
    write_json(PRIVATE, state)
    print(json.dumps({"stage": "completed", "cases": len(state["cases"])}), flush=True)


if __name__ == "__main__":
    run()
