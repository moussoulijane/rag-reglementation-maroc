"""Vérifier l'API sur HTTP local réel avec le corpus préparé, puis fermer le serveur."""

import json
import socket
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
import uvicorn

from rag_reglementation_maroc.api import create_app
from rag_reglementation_maroc.runtime import Settings

ROOT = Path(__file__).resolve().parents[1]


def main():
    app = create_app(
        Settings(
            data_dir=ROOT / "data",
            policy_path=ROOT / "evaluation/abstention_policy.json",
        )
    )
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
    worker = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    worker.start()
    checks = []
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{port}", timeout=5, trust_env=False
        ) as client:
            for _ in range(100):
                try:
                    if client.get("/ready").status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(0.1)
            else:
                raise RuntimeError("API non prête après le chargement du corpus.")
            assert client.get("/health").json()["ready"]
            for language, question in [("fr", "article 34"), ("ar", "المادة 34")]:
                response = client.post(
                    "/ask",
                    json={
                        "question": question,
                        "source_language": language,
                    },
                )
                response.raise_for_status()
                result = response.json()
                assert result["status"] == "evidence_found"
                assert result["citations"][0]["article_id"] == "34"
                assert result["citations"][0]["language"] == language
                checks.append(
                    {"language": language, "status": result["status"], "article_id": "34"}
                )
            result = client.post(
                "/ask",
                json={
                    "question": "Quel est le taux directeur actuel ?",
                },
            ).json()
            assert result["status"] == "abstained"
            checks.append({"scope": "current_information", "status": "abstained"})
        report = {
            "created_at_utc": datetime.now(UTC).isoformat(),
            "transport": "real HTTP on loopback; temporary server closed after checks",
            "corpus_articles": 394,
            "backend": "local",
            "encoder": "none",
            "checks": checks,
            "passed": True,
        }
        target = ROOT / "reports/api_smoke.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        server.should_exit = True
        worker.join(timeout=10)
        sock.close()
        if worker.is_alive():
            raise RuntimeError("Le serveur temporaire ne s'est pas arrêté.")


if __name__ == "__main__":
    main()
