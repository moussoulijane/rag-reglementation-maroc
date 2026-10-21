"""Serve the browser application without modifying the evaluated engine.

The original app factory owns its API routes and lifespan. This package only
adds a local capability description and static files, mounted after every API
route. Capabilities describe loaded objects; Ollama is never probed here.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from fastapi import FastAPI, HTTPException
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, Response
from starlette.staticfiles import StaticFiles

from rag_reglementation_maroc.api import SearchRequest, create_app
from rag_reglementation_maroc.catalog import SOURCE_CATALOG, SOURCES
from rag_reglementation_maroc.runtime import Settings

STATIC_DIR = Path(__file__).resolve().parent / "static"
SUPPORTED_LANGUAGES = ["fr", "ar"]


def _title(source_id: str, language: str, document_id: str | None = None) -> str:
    if source_id in SOURCE_CATALOG:
        return (
            "Loi bancaire 103-12 — version française"
            if language == "fr"
            else "Loi bancaire 103-12 — النسخة العربية"
        )
    return document_id or source_id


def _sources(articles: list) -> list[dict]:
    """Use loaded provenance, or explicitly uncounted catalogue entries."""
    if not articles:
        return [
            {
                "id": source.source_id,
                "language": source.language,
                "title": _title(source.source_id, source.language),
                "source_url": source.url,
                "version_date": source.version_date,
                "pdf_sha256": source.sha256,
                "article_count": None,
                "page_count": source.expected_pages,
            }
            for source in SOURCES
        ]
    result = {}
    for article in articles:
        source_id = article.source_id
        if source_id not in result:
            specification = SOURCE_CATALOG.get(source_id)
            catalogue_matches = specification is not None and (
                specification.sha256 == article.sha256
                and specification.url == article.source_url
                and specification.version_date == article.version_date
            )
            result[source_id] = {
                "id": source_id,
                "language": article.language,
                "title": _title(source_id, article.language, article.document_id),
                "source_url": article.source_url,
                "version_date": article.version_date,
                "pdf_sha256": article.sha256,
                "article_count": 0,
                "page_count": specification.expected_pages if catalogue_matches else None,
            }
        result[source_id]["article_count"] += 1
    return [result[key] for key in sorted(result)]


def _capabilities(application: FastAPI, settings: Settings) -> dict:
    service = getattr(application.state, "service", None)
    ready = service is not None
    retriever = getattr(service, "retriever", None)
    stored = getattr(retriever, "articles", {})
    articles = list(stored.values()) if isinstance(stored, dict) else list(stored)
    metadata = getattr(retriever, "metadata", {})
    encoder = getattr(retriever, "encoder", None)
    encoder_metadata = getattr(encoder, "metadata", {}) if encoder is not None else {}
    dimension = encoder_metadata.get("dimension")
    vectors = getattr(retriever, "vectors", None)
    if dimension is None and encoder is not None and getattr(vectors, "ndim", 0) == 2:
        dimension = int(vectors.shape[1])
    configured_ollama = getattr(service, "ollama", None)
    versions = sorted({article.version_date for article in articles})
    language_counts = Counter(article.language for article in articles)
    properties = SearchRequest.model_json_schema()["properties"]
    return {
        "schema_version": 1,
        "ready": ready,
        "corpus_version": versions[0] if len(versions) == 1 else "2022-03-31",
        "article_count": len(articles),
        "article_count_by_language": {
            language: language_counts.get(language, 0) for language in SUPPORTED_LANGUAGES
        },
        "sources": _sources(articles),
        "backend": metadata.get("backend", settings.backend),
        "encoder": {
            "configured": settings.encoder,
            "loaded": encoder is not None,
            "name": encoder_metadata.get("model", encoder_metadata.get("name")),
            "dimension": dimension,
            "preprocessing": encoder_metadata.get("preprocessing"),
        },
        "available_modes": (
            ["bm25", "semantic", "hybrid"]
            if ready and encoder is not None
            else ["bm25"]
            if ready
            else []
        ),
        "supported_languages": list(SUPPORTED_LANGUAGES),
        "policy_status": getattr(service, "policy_status", "explicit_or_illustrative")
        if ready
        else "unavailable",
        "generators": {
            "default": settings.generator,
            "choices": (
                ["extractive", "ollama"] if configured_ollama is not None else ["extractive"]
            )
            if ready
            else [],
            "ollama": {
                "configured": configured_ollama is not None,
                "model": getattr(configured_ollama, "model", settings.ollama_model),
                "availability": "not_checked",
                "probe_performed": False,
            },
        },
        "request_limits": {
            "question_min_length": properties["question"]["minLength"],
            "question_max_length": properties["question"]["maxLength"],
            "top_k_min": properties["top_k"]["minimum"],
            "top_k_max": properties["top_k"]["maximum"],
            "top_k_default": properties["top_k"]["default"],
        },
        "score_is_probability": False,
        "semantic_faithfulness_evaluated": False,
    }


class _Assets(StaticFiles):
    def __init__(self, *args, reserved_methods: dict[str, set[str]], **kwargs) -> None:
        self.reserved_methods = reserved_methods
        super().__init__(*args, **kwargs)

    async def check_config(self) -> None:
        # A checkout without an npm build must still start its API. Missing
        # assets are 404s; the index route below explains the missing build.
        if self.directory is not None and Path(self.directory).is_dir():
            await super().check_config()

    async def get_response(self, path: str, scope) -> Response:
        # Router method mismatches are partial matches. A later '/' mount would
        # otherwise consume GET /ask or POST /ready and turn the API's 405 into
        # an asset 404. Keep those original API responses intact as well.
        allowed = self.reserved_methods.get("/" + path.lstrip("/"))
        if allowed is not None and scope["method"] not in allowed:
            raise HTTPException(
                status_code=405,
                detail="Method Not Allowed",
                headers={"Allow": ", ".join(sorted(allowed))},
            )
        if self.directory is None or not Path(self.directory).is_dir():
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        return await super().get_response(path, scope)


def create_ui_app(
    settings: Settings | None = None,
    retriever=None,
    answer_service=None,
    *,
    static_dir: Path | None = None,
) -> FastAPI:
    config = settings or Settings.from_env()
    application = create_app(config, retriever=retriever, answer_service=answer_service)
    from rag_reglementation_assistant.api import install_routes

    install_routes(application, config, _capabilities)
    directory = Path(static_dir) if static_dir is not None else STATIC_DIR

    @application.get("/ui-config", include_in_schema=False)
    def ui_config():
        return _capabilities(application, config)

    @application.get("/", include_in_schema=False)
    def index():
        document = directory / "index.html"
        if not document.is_file():
            return HTMLResponse(
                "<!doctype html><html lang='fr'><meta charset='utf-8'>"
                "<title>Interface en préparation</title><h1>Interface en préparation</h1>"
                "<p>L’interface n’est pas encore préparée. "
                "L’API reste accessible dans sa <a href='/docs'>documentation</a>.</p></html>",
                status_code=503,
                headers={"Cache-Control": "no-store"},
            )
        return FileResponse(document, media_type="text/html", headers={"Cache-Control": "no-cache"})

    # Mount last: all original API routes, docs, and capability routes win.
    reserved = {
        route.path: set(route.methods)
        for route in application.routes
        if getattr(route, "methods", None) is not None
    }
    application.mount(
        "/",
        _Assets(directory=str(directory), check_dir=False, reserved_methods=reserved),
        name="ui-assets",
    )
    return application


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Interface locale de recherche documentaire FR/AR."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("Le port doit être compris entre 1 et 65535.")
    import uvicorn

    uvicorn.run("rag_reglementation_ui.app:app", host=args.host, port=args.port)
    return 0


app = create_ui_app()
