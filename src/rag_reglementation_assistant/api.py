"""Versioned assistant routes; all original API contracts remain available."""

from datetime import date
from threading import Lock
from typing import Literal

from fastapi import HTTPException

from rag_reglementation_maroc.api import SearchRequest

from .service import AssistantService


class AssistantRequest(SearchRequest):
    generator: Literal["extractive"] = "extractive"
    as_of: date | None = None
    institution_type: Literal["credit_institution", "bank", "payment_institution", "unknown"] = (
        "credit_institution"
    )


def install_routes(application, settings, capabilities):
    lock = Lock()

    def get_service():
        legacy = getattr(application.state, "service", None)
        if legacy is None:
            raise HTTPException(503, "Corpus de base indisponible.")
        with lock:
            service = getattr(application.state, "assistant_service", None)
            if service is None:
                try:
                    service = AssistantService(legacy, settings.data_dir)
                except (ValueError, FileNotFoundError, RuntimeError) as error:
                    raise HTTPException(
                        503, "Corpus métier indisponible ou intégrité invalide."
                    ) from error
                application.state.assistant_service = service
        return service

    @application.get("/assistant/config", include_in_schema=False)
    def assistant_config():
        base = capabilities(application, settings)
        if not base["ready"]:
            return {
                **base,
                "schema_version": 3,
                "profile": {
                    "domain_loaded": False,
                    "current_law_verified": False,
                    "independent_legal_review": False,
                },
                "corpus_label": "Documents non chargés",
            }
        return get_service().config(base)

    @application.post("/assistant/ask", include_in_schema=False)
    def assistant_ask(request: AssistantRequest):
        try:
            return get_service().ask(
                request.question,
                request.source_language,
                request.mode,
                request.top_k,
                request.generator,
                request.as_of.isoformat() if request.as_of else None,
                request.institution_type,
            )
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        except RuntimeError as error:
            raise HTTPException(503, "Recherche indisponible.") from error

    @application.post("/assistant/search", include_in_schema=False)
    def assistant_search(request: SearchRequest):
        try:
            hits = get_service().retriever.search(
                request.question,
                language=request.source_language,
                mode=request.mode,
                top_k=request.top_k,
            )
            return {
                "hits": [
                    {
                        "chunk_id": h.chunk.id,
                        "article_id": h.article.article_id,
                        "article_ref": h.article.id,
                        "language": h.article.language,
                        "text": h.chunk.text,
                        "score": h.score,
                        "score_is_probability": False,
                        "lexical_score": h.lexical_score,
                        "semantic_score": h.semantic_score,
                        "ranks": h.ranks,
                    }
                    for h in hits
                ]
            }
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @application.get("/assistant/schema", include_in_schema=False)
    def assistant_schema():
        return AssistantRequest.model_json_schema()

    return get_service
