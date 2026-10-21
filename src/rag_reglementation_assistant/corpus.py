"""Reproducible, hash-pinned extraction of a dated domain corpus.

The frozen law ingestion is reused. Additional articles come from the *recueil*,
never from the differently numbered individual scans. No download at startup.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import httpx
from pydantic import Field
from pypdf import PdfReader

from rag_reglementation_maroc.ingestion import load_articles
from rag_reglementation_maroc.models import Article


class DocumentaryArticle(Article):
    """Preserve source date precision instead of inventing a consolidation day."""

    version_date: str = Field(pattern=r"^\d{4}-\d{2}(?:-\d{2})?$")
    date_precision: str = "month"


RESOURCE_DIR = Path(__file__).parent / "resources"
RECUEIL_URL = "https://www.bkam.ma/content/download/814412/8935685/Recueil%20des%20textes%20l%C3%A9gislatifs%20et%20r%C3%A9glementaires%20de%20BAM%20_%20VF.pdf"
RECUEIL_SHA = "4855c4b2315510ff07463fad4a1a9206219760d7fde4b1564b2e52dc7d170a69"
SECTIONS = [
    {
        "id": "bam-mediation-2023-fr",
        "document_id": "circular-9-w-2016",
        "title": "Circulaire 9/W/2016 — recueil fin 2023",
        "pages": [1144, 1145],
        "article_count": 9,
        "publication_date": "2018-04-19",
    },
    {
        "id": "bam-complaints-2023-fr",
        "document_id": "circular-10-w-2016",
        "title": "Circulaire 10/W/2016 — recueil fin 2023",
        "pages": [1146, 1147, 1148],
        "article_count": 15,
        "publication_date": "2017-09-21",
    },
]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def download(data_dir: Path) -> Path:
    target = data_dir / "v3/raw/bam-recueil-2023-fr.pdf"
    if target.exists():
        if sha(target.read_bytes()) != RECUEIL_SHA:
            raise ValueError("Le recueil local ne correspond pas à l'empreinte approuvée.")
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=120, follow_redirects=True) as client:
        response = client.get(RECUEIL_URL)
        response.raise_for_status()
        content = response.content
    if not content.startswith(b"%PDF-") or sha(content) != RECUEIL_SHA:
        raise ValueError("PDF distant différent : nouvelle revue requise, aucun remplacement.")
    target.write_bytes(content)
    return target


def _body(page: str) -> str:
    # Headers/footnotes removed by their specific layout, not by legal content.
    page = page.replace("\r", "")
    lines = page.splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip() == "PUBLIC"), -1)
    if start < 0:
        raise ValueError("Mise en page du recueil inattendue.")
    lines = lines[start + 1 :]
    result = []
    for line in lines:
        if re.match(r"^43[34]\s+Arrêté", line.strip()):
            break
        result.append(line.rstrip())
    return "\n".join(result).strip()


def ingest(data_dir: Path) -> dict:
    path = data_dir / "v3/raw/bam-recueil-2023-fr.pdf"
    if not path.exists() or sha(path.read_bytes()) != RECUEIL_SHA:
        raise ValueError("Exécuter prepare-domain : PDF approuvé manquant ou différent.")
    reader = PdfReader(path)
    if len(reader.pages) != 1268:
        raise ValueError("Nombre de pages du recueil inattendu.")
    rows, page_maps = [], {}
    for section in SECTIONS:
        current_id, pieces = None, []

        def finish(section, current_id, pieces):
            if current_id is None:
                return
            text = "\n".join(piece for _, piece in pieces).strip()
            article = DocumentaryArticle(
                id=f"{section['id']}:article-{current_id}",
                source_id=section["id"],
                document_id=section["document_id"],
                article_id=current_id,
                language="fr",
                title=section["title"],
                text=text,
                page_start=min(p for p, _ in pieces),
                page_end=max(p for p, _ in pieces),
                version_date="2023-12",
                source_url=RECUEIL_URL,
                sha256=RECUEIL_SHA,
            )
            rows.append(article.model_dump())
            page_maps[article.id] = [{"page": p, "text": t} for p, t in pieces]

        for number in section["pages"]:
            text = _body(reader.pages[number - 1].extract_text() or "")
            markers = list(re.finditer(r"(?m)^Article (premier|\d+)\s*$", text))
            if current_id is not None and markers and text[: markers[0].start()].strip():
                pieces.append((number, text[: markers[0].start()].strip()))
            for i, marker in enumerate(markers):
                finish(section, current_id, pieces)
                current_id = "1" if marker[1] == "premier" else marker[1]
                end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
                pieces = [(number, text[marker.end() : end].strip())]
        finish(section, current_id, pieces)
        found = [r["article_id"] for r in rows if r["source_id"] == section["id"]]
        if found != [str(i) for i in range(1, section["article_count"] + 1)]:
            raise ValueError("Séquence d'articles inattendue.")
    output = data_dir / "v3/processed"
    output.mkdir(parents=True, exist_ok=True)
    blob = b"".join(canonical(row) + b"\n" for row in rows)
    (output / "articles.jsonl").write_bytes(blob)
    (output / "page_maps.json").write_bytes(canonical(page_maps))
    manifest = {
        "schema_version": 1,
        "corpus_id": "bam-client-relations-2023-v1",
        "pdf_sha256": RECUEIL_SHA,
        "articles_sha256": sha(blob),
        "page_maps_sha256": sha(canonical(page_maps)),
        "article_count": len(rows),
        "extraction": "pypdf-reviewed-recueil-sections-v1",
        "review": "internal_visual_comparison_2026-10-20",
        "independent_legal_review": False,
        "current_law_verified": False,
        "created_at": datetime.now(UTC).isoformat(),
        "article_hashes": {row["id"]: sha(row["text"].encode()) for row in rows},
    }
    (output / "quality.json").write_bytes(canonical(manifest))
    return manifest


def load_domain(data_dir: Path) -> tuple[list[Article], dict]:
    root = data_dir / "v3/processed"
    if not (root / "quality.json").exists():
        return [], {"domain_loaded": False}
    quality = json.loads((root / "quality.json").read_text(encoding="utf-8"))
    content = (root / "articles.jsonl").read_bytes()
    pages = (root / "page_maps.json").read_bytes()
    if (
        quality["pdf_sha256"] != RECUEIL_SHA
        or sha(content) != quality["articles_sha256"]
        or sha(pages) != quality["page_maps_sha256"]
    ):
        raise ValueError("Intégrité du corpus métier invalide.")
    pdf = data_dir / "v3/raw/bam-recueil-2023-fr.pdf"
    if not pdf.is_file() or sha(pdf.read_bytes()) != RECUEIL_SHA:
        raise ValueError("PDF de provenance manquant ou modifié.")
    rows = [DocumentaryArticle.model_validate_json(line) for line in content.splitlines()]
    expected = {
        f"{s['id']}:article-{i}" for s in SECTIONS for i in range(1, s["article_count"] + 1)
    }
    if {a.id for a in rows} != expected or len(rows) != 24:
        raise ValueError("Inventaire métier incomplet.")
    for row in rows:
        specification = next(item for item in SECTIONS if item["id"] == row.source_id)
        if (
            row.source_url != RECUEIL_URL
            or row.sha256 != RECUEIL_SHA
            or row.document_id != specification["document_id"]
            or row.language != "fr"
            or row.version_date != "2023-12"
            or row.date_precision != "month"
            or row.page_start not in specification["pages"]
            or row.page_end not in specification["pages"]
        ):
            raise ValueError("Provenance métier incompatible avec le catalogue.")
    return rows, {**quality, "domain_loaded": True, "page_maps": json.loads(pages)}


def load_corpus(data_dir: Path):
    law = load_articles(data_dir / "processed/articles.jsonl")
    additional, quality = load_domain(data_dir)
    return law + additional, quality


def source_catalog(articles: list[Article]) -> list[dict]:
    result = {}
    for article in articles:
        if article.source_id not in result:
            extra = next((s for s in SECTIONS if s["id"] == article.source_id), None)
            result[article.source_id] = {
                "id": article.source_id,
                "language": article.language,
                "title": article.title
                if extra
                else (
                    "Loi 103-12 — العربية" if article.language == "ar" else "Loi 103-12 — français"
                ),
                "source_url": article.source_url,
                "pdf_sha256": article.sha256,
                "version_date": article.version_date,
                "date_precision": "month" if extra else "day",
                "edition_label": "Recueil — fin 2023" if extra else "Loi — 31 mars 2022",
                "signature_date": "2016-06-10" if extra else None,
                "publication_date": extra["publication_date"] if extra else None,
                "effective_date": None,
                "current_law_verified": False,
                "article_count": 0,
                "page_count": 1268 if extra else 84,
                "page_range": extra["pages"] if extra else None,
                "review_status": "internal_visual" if extra else "internal_extraction",
                "official_arabic_version_loaded": False if extra else True,
                "version_relations": "individual_scan_differs_not_merged"
                if extra
                else "not_exhaustively_audited",
            }
        result[article.source_id]["article_count"] += 1
    return list(result.values())
