"""Explicit article headings and cache provenance are checked independently."""

import hashlib
import json

import pytest
from pydantic import ValidationError

from rag_reglementation_maroc import catalog, ingestion
from rag_reglementation_maroc.models import Article


def pages_with(entries):
    pages = [""] * 84
    for number, text in entries.items():
        pages[number - 1] = text
    return pages


def test_note_one_is_not_confused_with_the_real_article_111():
    pages = pages_with(
        {
            10: "10\nArticle 111\nFirst synthetic legal paragraph for article eleven.",
            53: "53\nArticle 111\nAnother synthetic paragraph for article one hundred eleven.",
        }
    )
    result = ingestion._extract_articles(pages, catalog.SOURCES[0], expected_ids=("11", "111"))
    assert [article.article_id for article in result] == ["11", "111"]
    assert [(a.page_start, a.page_end) for a in result] == [(10, 10), (53, 53)]


def test_article_19bis_and_192_keep_their_identity():
    pages = pages_with(
        {
            13: "Article 192\nSynthetic paragraph for article nineteen.\nArticle 19 bis3\nDistinct synthetic paragraph for article nineteen bis.",
            81: "Article 192\nA separate synthetic paragraph for the real article 192.",
        }
    )
    result = ingestion._extract_articles(
        pages, catalog.SOURCES[0], expected_ids=("19", "19bis", "192")
    )
    assert [article.article_id for article in result] == ["19", "19bis", "192"]


@pytest.mark.parametrize("label", ["1 11المادة", "1 11 المادة"])
def test_arabic_notes_and_bis_are_read_in_explicit_text_order(label):
    pages = pages_with(
        {
            10: label + "\nهذا نص اصطناعي لا يمثل مقتضيات قانونية حقيقية.",
            14: "3 المكررة19 المادة\nهذه فقرة اصطناعية ثانية للتحقق من رقم المادة.",
        }
    )
    result = ingestion._extract_articles(pages, catalog.SOURCES[1], expected_ids=("11", "19bis"))
    assert [article.article_id for article in result] == ["11", "19bis"]
    assert result[0].text.startswith("هذا نص")


def test_article_continuation_preserves_pdf_page_span_and_excludes_headers():
    pages = pages_with(
        {
            5: "LOI N° 103-12\nArticle premier\nA synthetic article begins here.",
            6: "6\nTITRE PREMIER : CHAMP D’APPLICATION ET CADRE\nINSTITUTIONNEL\nThe same article continues on this page.\nArticle 2\nThis is a different synthetic article.",
        }
    )
    result = ingestion._extract_articles(pages, catalog.SOURCES[0], expected_ids=("1", "2"))
    assert result[0].page_start == 5 and result[0].page_end == 6
    assert "continues" in result[0].text
    assert "INSTITUTIONNEL" not in result[0].text
    assert result[1].page_start == 6


def test_arabic_running_law_title_is_not_a_paragraph():
    pages = pages_with(
        {
            5: "103.12 القانون رقم\nالمادة الأولى\nهذا مثال اصطناعي لاختبار معالجة النصوص العربية.",
        }
    )
    result = ingestion._extract_articles(pages, catalog.SOURCES[1], expected_ids=("1",))
    assert "103.12" not in result[0].text


def test_missing_article_fails_instead_of_numbering_by_position():
    pages = pages_with({5: "Article premier\nA synthetic article with more than ten characters."})
    with pytest.raises(ValueError, match="missing=.*2"):
        ingestion._extract_articles(pages, catalog.SOURCES[0], expected_ids=("1", "2"))


def test_duplicate_explicit_heading_fails():
    pages = pages_with(
        {
            5: "Article premier\nSynthetic paragraph one.\nArticle premier\nSynthetic paragraph duplicate.",
        }
    )
    with pytest.raises(ValueError, match="duplicates"):
        ingestion._extract_articles(pages, catalog.SOURCES[0], expected_ids=("1",))


def test_unknown_title_does_not_silently_enter_the_previous_article():
    pages = pages_with({5: "Article 9999\nA synthetic paragraph under an impossible heading."})
    with pytest.raises(ValueError, match="Unknown article ID"):
        ingestion._extract_articles(pages, catalog.SOURCES[0], expected_ids=("1",))


def write_fixture_corpus(tmp_path, transform=None):
    records = []
    for source in catalog.SOURCES:
        for article_id in catalog.EXPECTED_ARTICLE_IDS:
            records.append(
                Article(
                    id=f"{source.source_id}:article-{article_id}",
                    document_id=source.document_id,
                    source_id=source.source_id,
                    article_id=article_id,
                    language=source.language,
                    title=f"Synthetic fixture {article_id}",
                    text="Synthetic content for schema verification only.",
                    source_url=source.url,
                    page_start=5,
                    page_end=5,
                    version_date=source.version_date,
                    sha256=source.sha256,
                ).model_dump()
            )
    if transform is not None:
        records = transform(records)
    raw = "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in records).encode("utf-8")
    path = tmp_path / "articles.jsonl"
    path.write_bytes(raw)
    quality = {
        "parser_version": ingestion.PARSER_VERSION,
        "articles_jsonl_sha256": hashlib.sha256(raw).hexdigest(),
        "article_count": len(records),
        "sources": [source.metadata() for source in catalog.SOURCES],
    }
    (tmp_path / "quality.json").write_text(json.dumps(quality), encoding="utf-8")
    return path


def test_load_checks_the_complete_bilingual_corpus(tmp_path):
    assert len(ingestion.load_articles(write_fixture_corpus(tmp_path))) == 394


def test_load_rejects_a_changed_text_cache(tmp_path):
    path = write_fixture_corpus(tmp_path)
    path.write_bytes(path.read_bytes().replace(b"Synthetic content", b"Altered content", 1))
    with pytest.raises(ValueError, match="cache checksum"):
        ingestion.load_articles(path)


def test_load_rejects_duplicates_even_when_report_hash_matches(tmp_path):
    path = write_fixture_corpus(tmp_path, lambda rows: rows + [rows[0]])
    with pytest.raises(ValueError, match="Duplicate article ID"):
        ingestion.load_articles(path)


def test_load_checks_pinned_source_fingerprint_even_with_matching_cache_hash(tmp_path):
    def alter(rows):
        rows[0]["sha256"] = "0" * 64
        return rows

    with pytest.raises(ValueError, match="Source fingerprint"):
        ingestion.load_articles(write_fixture_corpus(tmp_path, alter))


def test_load_validates_each_record_with_pydantic(tmp_path):
    def alter(rows):
        rows[0]["page_start"] = 0
        return rows

    with pytest.raises(ValidationError):
        ingestion.load_articles(write_fixture_corpus(tmp_path, alter))


def test_load_rejects_an_incomplete_source(tmp_path):
    with pytest.raises(ValueError, match="Incomplete or disordered"):
        ingestion.load_articles(write_fixture_corpus(tmp_path, lambda rows: rows[:-1]))


def test_load_requires_ingestion_quality_report(tmp_path):
    path = write_fixture_corpus(tmp_path)
    path.with_name("quality.json").unlink()
    with pytest.raises(ValueError, match="Missing quality"):
        ingestion.load_articles(path)


def test_ingestion_refuses_missing_sources(tmp_path):
    with pytest.raises(FileNotFoundError, match="download first"):
        ingestion.ingest_sources(tmp_path)
