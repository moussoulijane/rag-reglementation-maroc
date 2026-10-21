"""API réelle en mémoire, sans réseau ni corpus juridique versionné."""

from fastapi.testclient import TestClient

from rag_reglementation_maroc.answering import AnswerService
from rag_reglementation_maroc.api import create_app
from rag_reglementation_maroc.runtime import Settings


def test_health_readiness_and_utf8_citations(retriever):
    with TestClient(create_app(answer_service=AnswerService(retriever))) as client:
        assert client.get("/health").json()["ready"]
        assert client.get("/ready").status_code == 200
        response = client.post("/ask", json={"question": "المادة 34", "source_language": "ar"})
        assert response.status_code == 200
        assert response.json()["citations"][0]["language"] == "ar"
        assert "الاعتماد" in response.json()["answer"]
        assert client.post("/ask", json={"question": "  "}).status_code == 422
        unsupported = client.post("/search", json={"question": "agrément", "mode": "hybrid"})
        assert unsupported.status_code == 422


def test_missing_corpus_is_unready_without_implicit_download(tmp_path):
    with TestClient(create_app(Settings(data_dir=tmp_path))) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/health").json()["ready"] is False
        assert client.get("/ready").status_code == 503
        assert client.post("/ask", json={"question": "article 34"}).status_code == 503
        assert not list(tmp_path.iterdir())


def test_search_returns_full_provenance(retriever):
    with TestClient(create_app(answer_service=AnswerService(retriever))) as client:
        hit = client.post(
            "/search", json={"question": "article 34", "source_language": "fr"}
        ).json()["hits"][0]
        assert hit["source_id"] == "synthetic-fr"
        assert hit["document_id"] == "synthetic-law"
        assert hit["sha256"] == "a" * 64
