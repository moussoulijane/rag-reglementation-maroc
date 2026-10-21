"""Exercer le conteneur API réel, puis supprimer uniquement ce conteneur temporaire."""

import json
import re
import subprocess
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def docker(*args):
    result = subprocess.run(["docker", *args], cwd=ROOT, text=True, capture_output=True, check=True)
    return result.stdout.strip()


def main():
    name = "p2-bam-api-smoke-" + uuid.uuid4().hex[:8]
    container_id = None
    try:
        container_id = docker(
            "compose",
            "run",
            "-d",
            "--name",
            name,
            "-p",
            "127.0.0.1::8000",
            "-e",
            "RAG_ENCODER=none",
            "-e",
            "RAG_BACKEND=local",
            "-e",
            "RAG_GENERATOR=extractive",
            "api",
        )
        if not re.fullmatch(r"[0-9a-f]{64}", container_id):
            raise RuntimeError("Identifiant du conteneur temporaire inattendu.")
        inspection = json.loads(docker("inspect", container_id))[0]
        binding = inspection["NetworkSettings"]["Ports"]["8000/tcp"][0]
        assert binding["HostIp"] == "127.0.0.1"
        url = "http://127.0.0.1:" + binding["HostPort"]
        checks = []
        with httpx.Client(base_url=url, timeout=10, trust_env=False) as client:
            for _ in range(120):
                try:
                    if client.get("/ready").status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(0.5)
            else:
                raise RuntimeError(
                    "Conteneur API non prêt : " + docker("logs", container_id)[-3000:]
                )
            assert client.get("/health").status_code == 200
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
                    {"language": language, "article_id": "34", "status": "evidence_found"}
                )
            response = client.post("/ask", json={"question": "Quel est le taux directeur actuel ?"})
            response.raise_for_status()
            assert response.json()["status"] == "abstained"
            checks.append({"scope": "current_information", "status": "abstained"})
        report = {
            "created_at_utc": datetime.now(UTC).isoformat(),
            "image": inspection["Config"]["Image"],
            "image_id": inspection["Image"],
            "container_user": inspection["Config"]["User"],
            "corpus_articles": 394,
            "backend": "local",
            "encoder": "none",
            "generator": "extractive",
            "transport": "real Docker container HTTP on loopback",
            "checks": checks,
            "passed": True,
            "cleanup": "temporary container removed; image retained",
            "limits": "Integration smoke only; no relevance or generative faithfulness claim.",
        }
    finally:
        if container_id and re.fullmatch(r"[0-9a-f]{64}", container_id):
            docker("rm", "--force", container_id)
    target = ROOT / "reports/docker_smoke.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
