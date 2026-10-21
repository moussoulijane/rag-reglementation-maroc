"""API documentaire locale : recherche, citations et abstention."""

from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

from . import __version__
from .runtime import Settings, build_service


class SearchRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1500)
    source_language: Literal["fr", "ar"] | None = None
    mode: Literal["bm25", "semantic", "hybrid"] = "bm25"
    top_k: int = Field(default=5, ge=1, le=10)

    @field_validator("question")
    @classmethod
    def non_blank(cls, value):
        if len(value.strip()) < 3:
            raise ValueError("La question doit contenir au moins trois caractères utiles.")
        return value.strip()


class AskRequest(SearchRequest):
    generator: Literal["extractive", "ollama"] | None = None


def create_app(settings: Settings | None = None, retriever=None, answer_service=None) -> FastAPI:
    config = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(application):
        application.state.service = answer_service
        if application.state.service is None:
            try:
                application.state.service = build_service(config, retriever)
            except (FileNotFoundError, ValueError, RuntimeError, ImportError):
                application.state.service = None
        yield

    application = FastAPI(
        title="RAG Réglementation Maroc",
        version=__version__,
        description=(
            "Recherche FR/AR sur la loi bancaire 103-12, édition BAM du 31 mars 2022. "
            "Les citations renvoient aux PDF. Le corpus ne prouve pas le droit actuel."
        ),
        lifespan=lifespan,
    )

    def service():
        value = getattr(application.state, "service", None)
        if value is None:
            raise HTTPException(
                503, "Corpus ou modèle indisponible. Exécuter download puis ingest."
            )
        return value

    @application.get("/health")
    def health():
        return {
            "status": "ok",
            "ready": getattr(application.state, "service", None) is not None,
            "version": __version__,
            "corpus_version": "2022-03-31",
        }

    @application.get("/ready")
    def ready():
        value = service()
        return {"status": "ready", "retrieval": value.retriever.metadata}

    @application.post("/search")
    def search(request: SearchRequest):
        try:
            hits = service().retriever.search(
                request.question,
                language=request.source_language,
                mode=request.mode,
                top_k=request.top_k,
            )
            return {
                "hits": [
                    {
                        "chunk_id": hit.chunk.id,
                        "article_id": hit.article.article_id,
                        "source_id": hit.article.source_id,
                        "document_id": hit.article.document_id,
                        "sha256": hit.article.sha256,
                        "language": hit.article.language,
                        "text": hit.chunk.text,
                        "page_start": hit.article.page_start,
                        "page_end": hit.article.page_end,
                        "source_url": hit.article.source_url,
                        "version_date": hit.article.version_date,
                        "score": hit.score,
                        "score_is_probability": False,
                        "lexical_score": hit.lexical_score,
                        "semantic_score": hit.semantic_score,
                        "ranks": hit.ranks,
                    }
                    for hit in hits
                ]
            }
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        except RuntimeError as error:
            raise HTTPException(503, "Service de recherche indisponible.") from error

    @application.post("/ask")
    def ask(request: AskRequest):
        try:
            return service().ask(
                request.question,
                source_language=request.source_language,
                mode=request.mode,
                top_k=request.top_k,
                generator=request.generator or config.generator,
            )
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        except RuntimeError as error:
            raise HTTPException(503, "Service de recherche indisponible.") from error

    return application


app = create_app()
