"""UI wrapper contracts with synthetic documents and temporary static assets."""

import socket

import numpy as np
from fastapi.testclient import TestClient

from rag_reglementation_maroc.answering import AnswerService
from rag_reglementation_maroc.api import create_app
from rag_reglementation_maroc.catalog import SOURCES
from rag_reglementation_maroc.retrieval import LocalRetriever
from rag_reglementation_maroc.runtime import Settings
from rag_reglementation_ui.app import create_ui_app, main


def _assets(tmp_path):
    directory = tmp_path / "static"
    directory.mkdir()
    (directory / "assets").mkdir()
    (directory / "index.html").write_text(
        "<!doctype html><html lang='fr'><title>Interface test</title>FR / AR</html>",
        encoding="utf-8",
    )
    (directory / "assets/app.js").write_text("console.log('ui-test');", encoding="utf-8")
    (directory / "assets/app.css").write_text("body { color: #222; }", encoding="utf-8")
    return directory


def test_ui_remains_accessible_when_corpus_is_not_ready(tmp_path):
    data = tmp_path / "missing-data"
    application = create_ui_app(Settings(data_dir=data), static_dir=_assets(tmp_path))
    with TestClient(application) as client:
        index = client.get("/")
        assert index.status_code == 200
        assert index.headers["content-type"].startswith("text/html")
        assert "FR / AR" in index.text
        assert client.get("/health").json()["ready"] is False
        assert client.get("/ready").status_code == 503
        assert client.post("/ask", json={"question": "article 34"}).status_code == 503
        assert client.get("/docs").status_code == 200
        config = client.get("/ui-config").json()
        assert config["ready"] is False
        assert config["article_count"] == 0
        assert config["article_count_by_language"] == {"fr": 0, "ar": 0}
        assert config["available_modes"] == []
        assert config["generators"]["choices"] == []
        assert {entry["id"] for entry in config["sources"]} == {s.source_id for s in SOURCES}
        assert all(entry["article_count"] is None for entry in config["sources"])
        assert all(entry["page_count"] == 84 for entry in config["sources"])
    assert not data.exists()


def test_missing_build_is_friendly_and_does_not_break_original_api(tmp_path):
    application = create_ui_app(
        Settings(data_dir=tmp_path / "missing-data"), static_dir=tmp_path / "not-built"
    )
    with TestClient(application) as client:
        response = client.get("/")
        assert response.status_code == 503
        assert response.headers["content-type"].startswith("text/html")
        assert "Interface en préparation" in response.text
        assert str(tmp_path) not in response.text
        assert client.get("/assets/missing.js").status_code == 404
        assert client.get("/health").status_code == 200
        assert client.get("/ui-config").status_code == 200


def test_static_types_and_missing_assets_are_not_spa_html(tmp_path, retriever):
    application = create_ui_app(
        answer_service=AnswerService(retriever), static_dir=_assets(tmp_path)
    )
    with TestClient(application) as client:
        js = client.get("/assets/app.js")
        css = client.get("/assets/app.css")
        assert js.status_code == 200
        assert "javascript" in js.headers["content-type"]
        assert css.status_code == 200 and css.headers["content-type"].startswith("text/css")
        assert client.get("/assets/unknown.js").status_code == 404
        assert client.get("/unknown-page").status_code == 404
        assert "Interface test" not in client.get("/assets/unknown.js").text
        (tmp_path / "private.txt").write_text("PRIVATE", encoding="utf-8")
        assert client.get("/assets/%2e%2e/%2e%2e/private.txt").status_code == 404


def test_wrapper_keeps_every_original_api_response_and_schema(retriever, tmp_path):
    service = AnswerService(retriever)
    wrapped = create_ui_app(answer_service=service, static_dir=_assets(tmp_path))
    with TestClient(create_app(answer_service=service)) as base, TestClient(wrapped) as ui:
        for path in ("/health", "/ready", "/openapi.json"):
            assert ui.get(path).json() == base.get(path).json()
        request = {"question": "article 34", "source_language": "fr", "mode": "bm25"}
        assert ui.post("/search", json=request).json() == base.post("/search", json=request).json()
        original_answer = base.post("/ask", json=request).json()
        wrapped_answer = ui.post("/ask", json=request).json()
        original_answer.pop("latency_ms")
        wrapped_answer.pop("latency_ms")
        assert wrapped_answer == original_answer
        unsupported = {**request, "mode": "hybrid"}
        assert ui.post("/search", json=unsupported).status_code == 422
        assert base.post("/search", json=unsupported).status_code == 422
        assert ui.post("/ask", json={"question": "  "}).status_code == 422


def test_static_mount_preserves_original_method_not_allowed_responses(retriever, tmp_path):
    service = AnswerService(retriever)
    wrapped = create_ui_app(answer_service=service, static_dir=tmp_path / "not-built")
    with TestClient(create_app(answer_service=service)) as base, TestClient(wrapped) as ui:
        for method, path in (
            ("GET", "/ask"),
            ("GET", "/search"),
            ("POST", "/ready"),
            ("POST", "/health"),
            ("HEAD", "/health"),
            ("DELETE", "/search"),
        ):
            expected = base.request(method, path)
            actual = ui.request(method, path)
            assert actual.status_code == expected.status_code == 405
            assert actual.headers["allow"] == expected.headers["allow"]
            assert actual.content == expected.content


def test_bm25_config_reflects_loaded_synthetic_sources(retriever, tmp_path):
    application = create_ui_app(answer_service=AnswerService(retriever), static_dir=tmp_path)
    with TestClient(application) as client:
        config = client.get("/ui-config").json()
    assert config["ready"] is True
    assert config["article_count"] == 5
    assert config["article_count_by_language"] == {"fr": 3, "ar": 2}
    assert config["available_modes"] == ["bm25"]
    assert config["encoder"]["loaded"] is False
    assert config["encoder"]["name"] is None and config["encoder"]["dimension"] is None
    assert config["supported_languages"] == ["fr", "ar"]
    assert config["generators"]["choices"] == ["extractive"]
    assert config["score_is_probability"] is False
    assert config["request_limits"] == {
        "question_min_length": 3,
        "question_max_length": 1500,
        "top_k_min": 1,
        "top_k_max": 10,
        "top_k_default": 5,
    }
    sources = {source["id"]: source for source in config["sources"]}
    assert sources["synthetic-fr"]["article_count"] == 3
    assert sources["synthetic-ar"]["article_count"] == 2
    assert sources["synthetic-fr"]["source_url"] == "https://example.org/synthetic.pdf"
    assert sources["synthetic-fr"]["pdf_sha256"] == "a" * 64
    assert sources["synthetic-fr"]["page_count"] is None


class _SyntheticEncoder:
    metadata = {"name": "synthetic-ui-test", "preprocessing": "synthetic-only"}

    def split_offsets(self, text):
        return [(0, len(text))]

    def encode_documents(self, documents):
        return np.tile(np.array([1.0, 0.0]), (len(documents), 1))

    def encode_query(self, question):
        return np.array([1.0, 0.0])


def test_neural_config_uses_actual_loaded_encoder_dimension(articles, tmp_path):
    retriever = LocalRetriever(articles, _SyntheticEncoder())
    application = create_ui_app(
        Settings(encoder="multilingual"),
        answer_service=AnswerService(retriever),
        static_dir=tmp_path,
    )
    with TestClient(application) as client:
        config = client.get("/ui-config").json()
        response = client.post(
            "/search", json={"question": "permission", "source_language": "ar", "mode": "semantic"}
        )
    assert response.status_code == 200
    assert config["available_modes"] == ["bm25", "semantic", "hybrid"]
    assert config["encoder"] == {
        "configured": "multilingual",
        "loaded": True,
        "name": "synthetic-ui-test",
        "dimension": 2,
        "preprocessing": "synthetic-only",
    }


def test_ollama_is_only_described_never_probed(retriever, monkeypatch, tmp_path):
    class ConfiguredOllama:
        model = "test-local-model"

        def generate(self, *args, **kwargs):
            raise AssertionError("UI configuration must not call the generator.")

    def no_network(*args, **kwargs):
        raise AssertionError("UI configuration must not probe a service.")

    monkeypatch.setattr(socket, "create_connection", no_network)
    application = create_ui_app(
        answer_service=AnswerService(retriever, ollama=ConfiguredOllama()), static_dir=tmp_path
    )
    with TestClient(application) as client:
        config = client.get("/ui-config").json()
    assert config["generators"]["choices"] == ["extractive", "ollama"]
    assert config["generators"]["ollama"] == {
        "configured": True,
        "model": "test-local-model",
        "availability": "not_checked",
        "probe_performed": False,
    }


def test_ui_command_defaults_to_loopback_without_running_server(monkeypatch):
    captured = {}

    def run(application, **kwargs):
        captured.update({"application": application, **kwargs})

    monkeypatch.setattr("uvicorn.run", run)
    assert main([]) == 0
    assert captured == {
        "application": "rag_reglementation_ui.app:app",
        "host": "127.0.0.1",
        "port": 8000,
    }
