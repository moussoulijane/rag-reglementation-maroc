"""Download verified snapshots and extract articles without guessing their IDs."""

import hashlib
import json
import re
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from uuid import uuid4

from pypdf import PdfReader

from . import catalog
from .catalog import EXPECTED_ARTICLE_IDS, SourceSpec
from .models import Article

PARSER_VERSION = "bam-10312-20220331-v1"
MAX_PDF_BYTES = 20 * 1024 * 1024

# These exact PDF/page/title combinations were checked against the printed
# superscripts. The real articles 111 and 192 on other pages stay untouched.
_FR_ANNOTATED_TITLES = {
    (10, "Article 111"): "11",
    (13, "Article 192"): "19",
    (13, "Article 19 bis3"): "19bis",
    (14, "Article 214"): "21",
    (16, "Article 255"): "25",
    (17, "Article 266"): "26",
    (22, "Article 327"): "32",
    (24, "Article 348"): "34",
    (32, "Article 519"): "51",
    (36, "Article 6110"): "61",
    (54, "Article 11211"): "112",
}
_AR_ANNOTATED_TITLES = {
    (10, "1 11المادة"): "11",
    (13, "2 19المادة"): "19",
    (14, "3 المكررة19المادة"): "19bis",
    (14, "4 21المادة"): "21",
    (16, "5 25المادة"): "25",
    (17, "6 26المادة"): "26",
    (23, "7 32المادة"): "32",
    (24, "8 34المادة"): "34",
    (32, "9 51المادة"): "51",
    (37, "10 61المادة"): "61",
    (54, "11 112المادة"): "112",
}


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(text, encoding="utf-8", newline="\n")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _verified_bytes(path: Path, source: SourceSpec) -> bytes:
    data = path.read_bytes()
    if len(data) > MAX_PDF_BYTES or not data.startswith(b"%PDF-"):
        raise ValueError(f"Invalid PDF or oversized source: {source.source_id}")
    if hashlib.sha256(data).hexdigest() != source.sha256:
        raise ValueError(f"SHA-256 mismatch for {source.source_id}; refusing an unpinned edition.")
    return data


def download_sources(data_dir: Path) -> dict:
    """Download missing sources; verify cached bytes on every call.

    Normal HTTPS certificate verification remains enabled. A changed remote
    document fails checksum validation instead of silently changing the corpus.
    """
    raw = Path(data_dir) / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    records = []
    for source in catalog.SOURCES:
        target = raw / source.filename
        cached = target.exists()
        if not cached:
            request = Request(source.url, headers={"User-Agent": "rag-reglementation-maroc/0.1"})
            with urlopen(request, timeout=60) as response:
                final_url = urlparse(response.geturl())
                if final_url.scheme != "https" or final_url.hostname != "www.bkam.ma":
                    raise ValueError("Source redirected outside the official HTTPS domain.")
                data = response.read(MAX_PDF_BYTES + 1)
            if len(data) > MAX_PDF_BYTES or not data.startswith(b"%PDF-"):
                raise ValueError(f"Invalid PDF response for {source.source_id}")
            if hashlib.sha256(data).hexdigest() != source.sha256:
                raise ValueError(
                    f"SHA-256 mismatch for {source.source_id}; download not installed."
                )
            temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
            try:
                temporary.write_bytes(data)
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)
        data = _verified_bytes(target, source)
        records.append({**source.metadata(), "bytes": len(data), "cache_hit": cached})
    manifest = {
        "checked_at_utc": datetime.now(UTC).isoformat(),
        "edition_date": "2022-03-31",
        "sources": records,
    }
    _atomic_text(raw / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return manifest


def _article_heading(line: str, page: int, language: str) -> str | None:
    """Recognise explicit heading text, with audited page-specific note fixes."""
    compact = " ".join(line.split())
    if language == "fr":
        corrected = _FR_ANNOTATED_TITLES.get((page, compact))
        if corrected:
            return corrected
        match = re.fullmatch(r"Article (premier|[0-9]+)(?: (bis))?", compact)
        if match:
            number = "1" if match[1] == "premier" else match[1]
            return number + ("bis" if match[2] else "")
        if compact.startswith("Article "):
            raise ValueError(f"Unrecognised French article heading on PDF page {page}: {compact}")
        return None
    arabic_key = re.sub(r"\s+", "", compact)
    corrected = {
        (number, re.sub(r"\s+", "", title)): value
        for (number, title), value in _AR_ANNOTATED_TITLES.items()
    }.get((page, arabic_key))
    if corrected:
        return corrected
    if compact in {"المادة الأولى", "المادة الاولى"}:
        return "1"
    match = re.fullmatch(r"(?:المادة\s*([0-9]+)|([0-9]+)\s*المادة)", compact)
    if match:
        return match[1] or match[2]
    match = re.fullmatch(r"المادة\s*([0-9]+)\s*المكررة", compact)
    if match:
        return match[1] + "bis"
    if re.fullmatch(r"[0-9\s]*(?:المكررة\s*)?المادة[0-9\s]*(?:المكررة)?", compact):
        # A short standalone line containing this label should not disappear
        # into a preceding article if its ordering/footnote is unfamiliar.
        raise ValueError(f"Unrecognised Arabic article heading on PDF page {page}: {compact}")
    return None


def _extract_articles(
    pages: list[str], source: SourceSpec, *, expected_ids: tuple[str, ...] = EXPECTED_ARTICLE_IDS
) -> list[Article]:
    """Parse explicit headings; a count/order check detects omissions and ambiguity.

    ``expected_ids`` only supports isolated unit fixtures. Production ingestion
    always uses the complete pinned sequence and separately verifies PDF hashes.
    """
    articles: list[Article] = []
    article_id: str | None = None
    start_page = end_page = 0
    body: list[str] = []
    section_heading = False

    def finish() -> None:
        if article_id is None:
            return
        text = "\n".join(body).strip()
        articles.append(
            Article(
                id=f"{source.source_id}:article-{article_id}",
                document_id=source.document_id,
                source_id=source.source_id,
                article_id=article_id,
                language=source.language,
                title=(
                    f"Article {article_id}" if source.language == "fr" else f"المادة {article_id}"
                ),
                text=text,
                source_url=source.url,
                page_start=start_page,
                page_end=max(start_page, end_page),
                version_date=source.version_date,
                sha256=source.sha256,
            )
        )

    for page_number, page_text in enumerate(pages, 1):
        if page_number < 5:
            continue  # Covers and the editorial list of amending laws.
        lines = page_text.splitlines()
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            compact = " ".join(stripped.split())
            heading = _article_heading(compact, page_number, source.language)
            if heading is not None:
                if heading not in EXPECTED_ARTICLE_IDS:
                    raise ValueError(f"Unknown article ID {heading} on PDF page {page_number}")
                finish()
                article_id, start_page, end_page = heading, page_number, page_number
                body = []
                section_heading = False
                continue
            # Running page titles and printed folios are not legal paragraphs.
            if (
                compact == str(page_number)
                or compact == "LOI N° 103-12"
                or re.fullmatch(r"(?:103\.12\s*)?القانون رقم(?:\s*103\.12)?", compact)
            ):
                continue
            if source.language == "fr":
                if re.match(r"^TITRE (?:PREMIER|[IVX]+)\s*:", compact):
                    continue
                if compact.isupper() and any(char.isalpha() for char in compact):
                    if re.fullmatch(r"TITRE (?:PREMIER|[IVX]+)", compact):
                        section_heading = True
                    continue
                if re.match(r"^(?:Chapitre|Section)\b", compact):
                    section_heading = True
                    continue
            else:
                if re.match(r"^القسم .*[-–]", compact):
                    continue
                if re.fullmatch(r"(?:القسم|الباب) [^ ]+", compact):
                    section_heading = True
                    continue
            if section_heading or article_id is None:
                continue
            body.append(stripped)
            end_page = page_number
    finish()
    found = tuple(article.article_id for article in articles)
    if found != expected_ids:
        missing = sorted(set(expected_ids) - set(found))
        duplicates = sorted({item for item in found if found.count(item) > 1})
        raise ValueError(
            f"Invalid article sequence for {source.source_id}: {len(found)} headings; "
            f"missing={missing}, duplicates={duplicates}. Review source/layout instead of guessing IDs."
        )
    return articles


def ingest_sources(data_dir: Path) -> list[Article]:
    """Extract all 394 articles from the two verified official PDF editions."""
    data_dir = Path(data_dir)
    articles: list[Article] = []
    source_quality = []
    for source in catalog.SOURCES:
        path = data_dir / "raw" / source.filename
        if not path.exists():
            raise FileNotFoundError(f"Missing source {path}; run download first.")
        data = _verified_bytes(path, source)
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted or len(reader.pages) != source.expected_pages:
            raise ValueError(f"Unexpected PDF structure for {source.source_id}")
        pages = [page.extract_text() or "" for page in reader.pages]
        source_articles = _extract_articles(pages, source)
        articles.extend(source_articles)
        source_quality.append(
            {
                **source.metadata(),
                "actual_pages": len(pages),
                "articles": len(source_articles),
                "extracted_characters": sum(len(page) for page in pages),
                "empty_pdf_pages": [
                    index + 1 for index, text in enumerate(pages) if not text.strip()
                ],
            }
        )
    jsonl = "".join(article.model_dump_json() + "\n" for article in articles)
    processed = data_dir / "processed"
    _atomic_text(processed / "articles.jsonl", jsonl)
    quality = {
        "parser_version": PARSER_VERSION,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "edition_date": "2022-03-31",
        "article_count": len(articles),
        "expected_per_language": len(EXPECTED_ARTICLE_IDS),
        "articles_jsonl_sha256": hashlib.sha256(jsonl.encode("utf-8")).hexdigest(),
        "sources": source_quality,
        "limitations": [
            "Dated documentary snapshot; current legal validity is not established.",
            "Footnotes remain in extracted bodies and may be attached to the last article on a page.",
            "PDF page references, not alignment by page number, connect the French and Arabic versions.",
            "Extracted Arabic preserves PDF text order; search normalization must not overwrite citations.",
        ],
    }
    _atomic_text(
        processed / "quality.json", json.dumps(quality, ensure_ascii=False, indent=2) + "\n"
    )
    return articles


def load_articles(path: Path) -> list[Article]:
    """Load a complete corpus with schema, provenance and cache-integrity checks."""
    path = Path(path)
    raw = path.read_bytes()
    quality_path = path.with_name("quality.json")
    if not quality_path.is_file():
        raise ValueError("Missing quality.json; regenerate the corpus with ingest.")
    quality = json.loads(quality_path.read_text(encoding="utf-8"))
    if not isinstance(quality, dict):
        raise ValueError("Quality report must be a JSON object.")
    if quality.get("parser_version") != PARSER_VERSION:
        raise ValueError("Unsupported ingestion report; regenerate the corpus.")
    if quality.get("articles_jsonl_sha256") != hashlib.sha256(raw).hexdigest():
        raise ValueError("Article cache checksum mismatch; regenerate the corpus.")
    records = raw.decode("utf-8").splitlines()
    if not records or any(not line.strip() for line in records):
        raise ValueError("Empty corpus or blank JSONL record.")
    articles = [Article.model_validate_json(line) for line in records]
    seen: set[str] = set()
    by_source: dict[str, list[str]] = {source.source_id: [] for source in catalog.SOURCES}
    source_catalog = {source.source_id: source for source in catalog.SOURCES}
    for article in articles:
        if article.id in seen:
            raise ValueError(f"Duplicate article ID: {article.id}")
        seen.add(article.id)
        source = source_catalog.get(article.source_id)
        if source is None:
            raise ValueError(f"Uncatalogued source: {article.source_id}")
        if (
            article.document_id != source.document_id
            or article.language != source.language
            or article.source_url != source.url
            or article.sha256 != source.sha256
            or article.version_date != source.version_date
            or article.page_start < 5
            or article.page_end > source.expected_pages
        ):
            raise ValueError(f"Source fingerprint mismatch: {article.id}")
        by_source[source.source_id].append(article.article_id)
    for source_id, found in by_source.items():
        if tuple(found) != EXPECTED_ARTICLE_IDS:
            raise ValueError(f"Incomplete or disordered corpus for {source_id}")
    expected_fingerprints = {source.source_id: source.sha256 for source in catalog.SOURCES}
    source_reports = quality.get("sources")
    if not isinstance(source_reports, list) or not all(
        isinstance(item, dict) and "source_id" in item and "sha256" in item
        for item in source_reports
    ):
        raise ValueError("Quality report source fingerprints are malformed.")
    actual_fingerprints = {item["source_id"]: item["sha256"] for item in source_reports}
    if expected_fingerprints != actual_fingerprints or quality.get("article_count") != len(
        articles
    ):
        raise ValueError("Quality report source fingerprints/count do not match the catalog.")
    return articles
