import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from rag_reglementation_assistant.retrieval import DomainRetriever
from rag_reglementation_assistant.review import evaluate_reserved, freeze_reserved, import_review
from rag_reglementation_maroc.models import Article
from rag_reglementation_maroc.retrieval import LocalRetriever


class Encoder:
    metadata = {"name": "synthetic-vector-reuse-only"}

    def __init__(self):
        self.calls = []

    def split_offsets(self, text):
        return [(0, len(text))]

    def encode_documents(self, texts):
        self.calls.append(len(texts))
        return np.tile([1.0, 0.0], (len(texts), 1))

    def encode_query(self, text):
        return np.array([1.0, 0.0])


def a(id, text):
    return Article(
        id=f"{id}:article-1",
        source_id=id,
        article_id="1",
        document_id=id,
        language="fr",
        title="Synthetic",
        text=text,
        page_start=1,
        page_end=1,
        version_date="2023-12-31",
        sha256="a" * 64,
        source_url="https://example.org/synthetic.pdf",
    )


def test_only_new_passages_are_encoded_and_domain_cache_is_reused(tmp_path):
    encoder = Encoder()
    base = LocalRetriever(
        [a("one", "Premier article synthétique."), a("two", "Deuxième article synthétique.")],
        encoder,
    )
    original = base.vectors.copy()
    result = DomainRetriever(base, [a("three", "Nouveau passage synthétique.")], tmp_path)
    assert encoder.calls == [2, 1]
    assert np.array_equal(result.vectors[:2], original)
    again = DomainRetriever(base, [a("three", "Nouveau passage synthétique.")], tmp_path)
    assert encoder.calls == [2, 1]
    assert again.metadata["frozen_vectors_reused"] == 2


def test_reserved_freeze_requires_real_review_declaration_and_nonempty_cases(tmp_path):
    suite = tmp_path / "cases.json"
    suite.write_text(json.dumps({"status": "development", "cases": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="humaine"):
        freeze_reserved(SimpleNamespace(), suite, tmp_path / "manifest.json")


def test_semantic_review_cannot_skip_rows_or_leave_claims_unreviewed(tmp_path):
    result = tmp_path / "results.json"
    result.write_text(
        json.dumps({"rows": [{"id": "synthetic:0", "emitted_claim_ids": ["synthetic-claim"]}]}),
        encoding="utf-8",
    )
    review = tmp_path / "review.json"
    content = {
        "reviewer": "SYNTHETIC UNIT TEST ONLY",
        "competence": "synthetic",
        "independent_from_implementation": True,
        "rows": [],
    }
    review.write_text(json.dumps(content), encoding="utf-8")
    with pytest.raises(ValueError, match="Toutes"):
        import_review(result, review, tmp_path / "summary.json")
    content["rows"] = [
        {
            "id": "synthetic:0",
            "claim_verdicts": {"synthetic-claim": None},
            "coverage": 1.0,
            "critical_error": False,
            "status_appropriate": True,
        }
    ]
    review.write_text(json.dumps(content), encoding="utf-8")
    with pytest.raises(ValueError, match="relues"):
        import_review(result, review, tmp_path / "summary.json")
    content["rows"][0]["claim_verdicts"]["synthetic-claim"] = "supported"
    review.write_text(json.dumps(content), encoding="utf-8")
    summary = import_review(result, review, tmp_path / "summary.json")
    assert summary["claim_support_rate"] == 1.0
    assert "not_authenticated" in summary["status"]


def test_frozen_test_rejects_changed_questions_or_retrieval_mode(tmp_path):
    service = SimpleNamespace(
        articles={"one": a("one", "Texte synthétique pour un test de gel.")},
        retriever=SimpleNamespace(metadata={"synthetic": True}),
    )
    suite = {
        "status": "reserved_test",
        "annotation_review": {
            "kind": "external_human",
            "reviewer": "SYNTHETIC UNIT TEST ONLY",
            "competence": "synthetic",
            "rankings_consulted": False,
            "semantic_overlap_audited": True,
            "independent_from_implementation": True,
        },
        "cases": [
            {
                "group_id": "synthetic-new",
                "variants": [
                    {
                        "query_language": "fr",
                        "source_language": "fr",
                        "question": "Question synthétique",
                        "expected_status": "absent",
                    }
                ],
            }
        ],
    }
    cases = tmp_path / "cases.json"
    cases.write_text(json.dumps(suite), encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    freeze_reserved(service, cases, manifest, mode="bm25")
    with pytest.raises(ValueError, match="différents"):
        evaluate_reserved(
            service,
            cases,
            manifest,
            tmp_path / "report",
            Path("outputs/synthetic-unwritten"),
            mode="semantic",
        )
    suite["cases"][0]["variants"][0]["question"] = "Question modifiée"
    cases.write_text(json.dumps(suite), encoding="utf-8")
    with pytest.raises(ValueError, match="différents"):
        evaluate_reserved(
            service,
            cases,
            manifest,
            tmp_path / "report",
            Path("outputs/synthetic-unwritten"),
            mode="bm25",
        )
