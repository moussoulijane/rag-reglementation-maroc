"""Contrats partagés : l'article original, son passage et sa provenance."""

from dataclasses import dataclass, field
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Article(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    document_id: str
    source_id: str
    article_id: str
    language: Literal["fr", "ar"]
    title: str
    text: str = Field(min_length=10)
    source_url: str
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    version_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def check_provenance(self) -> Self:
        if self.page_end < self.page_start:
            raise ValueError("La dernière page ne peut pas précéder la première.")
        if self.id != f"{self.source_id}:article-{self.article_id}":
            raise ValueError("L'identifiant doit relier la source à l'article.")
        return self


class Chunk(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    article_ref: str
    text: str = Field(min_length=1)
    char_start: int = Field(ge=0)
    char_end: int = Field(gt=0)

    @model_validator(mode="after")
    def check_offsets(self) -> Self:
        if self.char_end <= self.char_start:
            raise ValueError("Les offsets doivent délimiter un passage non vide.")
        return self


@dataclass(frozen=True)
class SearchHit:
    chunk: Chunk
    article: Article
    score: float
    lexical_score: float | None = None
    semantic_score: float | None = None
    ranks: dict[str, int] = field(default_factory=dict)
