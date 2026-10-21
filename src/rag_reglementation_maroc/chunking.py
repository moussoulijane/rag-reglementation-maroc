"""Passages avec offsets exacts dans le texte original."""

from .models import Article, Chunk


def character_offsets(text: str, size: int = 650, overlap: int = 100) -> list[tuple[int, int]]:
    if size <= 0 or not 0 <= overlap < size:
        raise ValueError("Le recouvrement doit être inférieur à la taille.")
    offsets = []
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        if end < len(text):
            boundary = text.rfind(" ", start + size // 2, end)
            if boundary > start:
                end = boundary
        offsets.append((start, end))
        if end == len(text):
            break
        start = max(start + 1, end - overlap)
    return offsets


def build_chunks(articles: list[Article], encoder=None) -> list[Chunk]:
    chunks = []
    for article in articles:
        offsets = (
            encoder.split_offsets(article.text)
            if encoder is not None
            else character_offsets(article.text)
        )
        for index, (start, end) in enumerate(offsets):
            if not 0 <= start < end <= len(article.text):
                raise ValueError("Offsets invalides.")
            chunks.append(
                Chunk(
                    id=f"{article.id}:chunk-{index}",
                    article_ref=article.id,
                    text=article.text[start:end],
                    char_start=start,
                    char_end=end,
                )
            )
    return chunks
