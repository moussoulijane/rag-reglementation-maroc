"""Invariants du classement, du découpage et du cache."""

import numpy as np
import pytest

from rag_reglementation_maroc.chunking import build_chunks, character_offsets
from rag_reglementation_maroc.retrieval import LocalRetriever, reciprocal_rank_fusion
from rag_reglementation_maroc.text import normalize, requested_article


def test_article_lookup_handles_real_111_and_note_context_is_not_changed_here(retriever):
    assert retriever.search("article 34", language="fr")[0].article.article_id == "34"
    assert retriever.search("article 111", language="fr") == []
    assert requested_article("المادة ١٩ المكررة") == "19bis"


def test_normalization_preserves_search_equivalence():
    assert normalize("Établissement") == "etablissement"
    assert normalize("إِئْتِمَان") == normalize("ايتمان")


def test_chunks_are_exact_substrings_with_overlap_and_complete_coverage(articles):
    text = ("Un long texte de test avec de vraies limites. " * 40).strip()
    article = articles[0].model_copy(update={"text": text})
    chunks = build_chunks([article])
    assert chunks[0].char_start == 0
    assert chunks[-1].char_end == len(text)
    for previous, current in zip(chunks, chunks[1:], strict=False):
        assert current.char_start < previous.char_end
    assert all(c.text == text[c.char_start : c.char_end] for c in chunks)
    with pytest.raises(ValueError):
        character_offsets(text, size=100, overlap=100)


def test_language_filter_deduplicates_articles_and_unknown_terms_do_not_fill_results(retriever):
    hits = retriever.search("agrément banques", language="fr")
    assert hits[0].article.article_id == "34"
    assert all(hit.article.language == "fr" for hit in hits)
    assert len({hit.article.id for hit in hits}) == len(hits)
    assert retriever.search("xyzzqvunrelated") == []


def test_no_silent_fallback_without_neural_model(retriever):
    with pytest.raises(ValueError, match="encodeur"):
        retriever.search("agrément", mode="hybrid")


def test_rrf_uses_ranks_and_rejects_duplicate_ids():
    fused = reciprocal_rank_fusion([[1, 2], [2, 1]])
    assert fused[1] == fused[2]
    with pytest.raises(ValueError):
        reciprocal_rank_fusion([[1, 1]])


class SyntheticEncoder:
    metadata = {"name": "synthetic-test-only", "revision": "1"}
    calls = 0

    def split_offsets(self, text):
        return [(0, len(text))]

    def encode_documents(self, texts):
        self.calls += 1
        return np.array(
            [[1.0, 0.0] if ("agrément" in t or "الاعتماد" in t) else [0.0, 1.0] for t in texts]
        )

    def encode_query(self, text):
        return np.array([1.0, 0.0])


def test_semantic_cache_and_cross_language_filter(articles, tmp_path):
    encoder = SyntheticEncoder()
    retriever = LocalRetriever(articles, encoder, tmp_path)
    assert (
        retriever.search("permission", language="ar", mode="semantic")[0].article.article_id == "34"
    )
    assert encoder.calls == 1
    LocalRetriever(articles, encoder, tmp_path)
    assert encoder.calls == 1
    assert retriever.metadata["encoder"]["name"] == "synthetic-test-only"
