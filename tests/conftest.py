"""Documents synthétiques originaux, sans reproduction du corpus BAM."""

import pytest

from rag_reglementation_maroc.models import Article
from rag_reglementation_maroc.retrieval import LocalRetriever


@pytest.fixture
def articles():
    texts = [
        ("fr", "34", "Agrément", "L'agrément des banques est accordé par l'autorité Exemple."),
        ("fr", "155", "Agence", "La fermeture d'une agence exige de prévenir les clients."),
        (
            "fr",
            "157",
            "Réclamations",
            "Un service interne reçoit les réclamations écrites des clients.",
        ),
        ("ar", "34", "الاعتماد", "تمنح السلطة المختصة الاعتماد للمؤسسات البنكية في هذا المثال."),
        ("ar", "155", "الوكالة", "يجب إخبار العملاء قبل إغلاق وكالة بنكية في هذا المثال."),
    ]
    return [
        Article(
            id=f"synthetic-{language}:article-{number}",
            document_id="synthetic-law",
            source_id=f"synthetic-{language}",
            article_id=number,
            language=language,
            title=title,
            text=text,
            source_url="https://example.org/synthetic.pdf",
            page_start=1,
            page_end=2,
            version_date="2022-03-31",
            sha256="a" * 64,
        )
        for language, number, title, text in texts
    ]


@pytest.fixture
def retriever(articles):
    return LocalRetriever(articles)
