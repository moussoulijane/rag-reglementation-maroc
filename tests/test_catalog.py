"""Catalog and cache tests use synthetic bytes; no network is needed."""

import hashlib
import json

import pytest

from rag_reglementation_maroc import catalog, ingestion
from rag_reglementation_maroc.catalog import SourceSpec


def test_catalog_has_two_dated_official_editions():
    assert {source.language for source in catalog.SOURCES} == {"fr", "ar"}
    assert len(catalog.EXPECTED_ARTICLE_IDS) == 197
    assert catalog.EXPECTED_ARTICLE_IDS[18:21] == ("19", "19bis", "20")
    assert catalog.EXPECTED_ARTICLE_IDS[-1] == "196"
    for source in catalog.SOURCES:
        assert source.url.startswith("https://www.bkam.ma/")
        assert source.version_date == "2022-03-31"
        assert source.expected_pages == 84
        assert len(source.sha256) == 64


def test_verified_cache_is_used_without_a_network_call(tmp_path, monkeypatch):
    payload = b"%PDF-1.7\nSynthetic cache fixture, not a Bank Al-Maghrib document."
    source = SourceSpec(
        "fixture-fr",
        "fr",
        "https://www.bkam.ma/fixture.pdf",
        hashlib.sha256(payload).hexdigest(),
        "fixture.pdf",
    )
    monkeypatch.setattr(catalog, "SOURCES", (source,))
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / source.filename).write_bytes(payload)

    def forbidden(*args, **kwargs):
        raise AssertionError("Tests must not access the network")

    monkeypatch.setattr(ingestion, "urlopen", forbidden)
    manifest = ingestion.download_sources(tmp_path)
    assert manifest["sources"][0]["cache_hit"] is True
    assert manifest["sources"][0]["sha256"] == source.sha256
    assert json.loads((raw / "manifest.json").read_text())["edition_date"] == "2022-03-31"


def test_tampered_cache_fails_instead_of_redownloading(tmp_path, monkeypatch):
    source = catalog.SOURCES[0]
    monkeypatch.setattr(catalog, "SOURCES", (source,))
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / source.filename).write_bytes(b"%PDF-1.7\nChanged PDF bytes")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        ingestion.download_sources(tmp_path)


def test_non_pdf_response_cannot_become_a_cached_source(tmp_path):
    source = catalog.SOURCES[0]
    path = tmp_path / "source.pdf"
    path.write_bytes(b"<html>an error page</html>")
    with pytest.raises(ValueError, match="Invalid PDF"):
        ingestion._verified_bytes(path, source)


def test_download_verifies_remote_checksum_before_installing_cache(tmp_path, monkeypatch):
    from io import BytesIO

    source = catalog.SOURCES[0]
    monkeypatch.setattr(catalog, "SOURCES", (source,))

    class Response(BytesIO):
        def geturl(self):
            return source.url

    monkeypatch.setattr(
        ingestion, "urlopen", lambda *args, **kwargs: Response(b"%PDF-1.7\nWrong synthetic content")
    )
    with pytest.raises(ValueError, match="download not installed"):
        ingestion.download_sources(tmp_path)
    assert not (tmp_path / "raw" / source.filename).exists()
