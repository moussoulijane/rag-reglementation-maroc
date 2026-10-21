"""Offline encoder contracts; real inference is an explicit opt-in check."""

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from rag_reglementation_maroc.embeddings import (
    DIMENSION,
    MODEL_FILES,
    MODEL_REPOSITORY,
    MODEL_REVISION,
    MultilingualEncoder,
    _normalized_with_offsets,
    _sha256,
    normalize_model_text,
)


class CharacterTokenizer:
    def no_truncation(self):
        pass

    def no_padding(self):
        pass

    def encode(self, text, add_special_tokens=True):
        offsets = [
            (position, position + 1) for position, char in enumerate(text) if not char.isspace()
        ]
        ids = [1] * (len(offsets) + (2 if add_special_tokens else 0))
        return SimpleNamespace(offsets=offsets, ids=ids)


class FakeModel:
    def embed(self, documents, batch_size=32):
        return [np.ones(DIMENSION) for _ in documents]


@pytest.fixture
def encoder():
    result = MultilingualEncoder.__new__(MultilingualEncoder)
    result.preprocessing = "normalized"
    result._tokenizer = CharacterTokenizer()
    result._model = FakeModel()
    result._metadata = {"revision": MODEL_REVISION, "files_sha256": {"tokenizer.json": "abc"}}
    return result


def test_missing_model_fails_before_optional_import_or_network(tmp_path):
    with pytest.raises(RuntimeError, match="aucun téléchargement automatique"):
        MultilingualEncoder(tmp_path)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "text",
    ["  agrément des banques et sociétés financières  ", "  الترخيص لمؤسسات الائتمان بالمغرب  "],
)
def test_offsets_preserve_original_french_arabic_text(encoder, text):
    spans = encoder.split_offsets(text, max_tokens=10, overlap=2)
    assert spans[0][0] == 0
    assert spans[-1][1] == len(text)
    assert all(0 <= start < end <= len(text) for start, end in spans)
    assert all(
        next_start <= end for (_, end), (next_start, _) in zip(spans, spans[1:], strict=False)
    )
    for start, end in spans:
        assert text[start:end]
        assert len(encoder._tokenizer.encode(text[start:end], add_special_tokens=False).ids) <= 10


def test_empty_and_whitespace_offsets(encoder):
    assert encoder.split_offsets("") == []
    assert encoder.split_offsets("   ") == [(0, 3)]


@pytest.mark.parametrize("max_tokens,overlap", [(0, 0), (127, 0), (10, -1), (10, 10)])
def test_invalid_chunk_token_parameters(encoder, max_tokens, overlap):
    with pytest.raises(ValueError):
        encoder.split_offsets("texte", max_tokens, overlap)


def test_encode_shapes_and_normalization(encoder):
    assert encoder.encode_documents([]).shape == (0, 384)
    documents = encoder.encode_documents(["banque", "بنك"])
    assert documents.shape == (2, 384)
    np.testing.assert_allclose(np.linalg.norm(documents, axis=1), 1, atol=1e-6)
    assert encoder.encode_query("agrément").shape == (384,)


@pytest.mark.parametrize("text", ["", "   ", "x" * 127])
def test_empty_or_over_limit_is_rejected_instead_of_truncated(encoder, text):
    with pytest.raises(ValueError):
        encoder.encode_query(text)


def test_metadata_returns_independent_copy(encoder):
    metadata = encoder.metadata
    metadata["files_sha256"]["tokenizer.json"] = "changed"
    assert encoder.metadata["files_sha256"]["tokenizer.json"] == "abc"


def test_pdf_normalization_expands_ligatures_removes_tatweel_and_format_controls():
    text = "\u202bوالــي بنــك المغــرب\u202c \ufefb \ufb01 e\u0301\u00ad"
    normalized, offsets = _normalized_with_offsets(text)
    assert normalized == "والي بنك المغرب لا fi é"
    assert len(offsets) == len(normalized)
    assert all(0 <= start < end <= len(text) for start, end in offsets)
    assert text[offsets[-1][0] : offsets[-1][1]] == "e\u0301"


def test_encoder_uses_same_normalized_input_for_documents_and_questions(encoder):
    captured = []

    class CapturingModel:
        def embed(self, documents, batch_size=32):
            captured.extend(documents)
            return [np.ones(DIMENSION) for _ in documents]

    encoder._model = CapturingModel()
    encoder.encode_documents(["بنــك \ufb01\u00ad"])
    encoder.encode_query("\u202bبنــك\u202c")
    assert captured == ["بنك fi", "بنك"]


def test_raw_mode_preserves_input_and_offsets_exactly(encoder):
    encoder.preprocessing = "raw"
    captured = []

    class CapturingModel:
        def embed(self, documents, batch_size=32):
            captured.extend(documents)
            return [np.ones(DIMENSION) for _ in documents]

    encoder._model = CapturingModel()
    text = "\u202bبنــك\u202c \ufb01\u00ad"
    encoder.encode_documents([text])
    encoder.encode_query(text)
    assert captured == [text, text]
    prepared, identity = encoder._prepare_text(text)
    assert prepared == text
    assert identity == [(position, position + 1) for position in range(len(text))]
    expected = [(0, 5), (4, len(text))]
    assert encoder.split_offsets(text, max_tokens=5, overlap=1) == expected


def test_constructor_raw_metadata_reproduces_v1_signature(tmp_path, monkeypatch):
    import rag_reglementation_maroc.embeddings as module

    monkeypatch.setattr(
        module.MultilingualEncoder, "_verify_snapshot", lambda self: {"files_sha256": {}}
    )
    monkeypatch.setattr(module, "version", lambda package: "unit-test")
    monkeypatch.setitem(
        sys.modules, "fastembed", SimpleNamespace(TextEmbedding=lambda **kwargs: FakeModel())
    )
    monkeypatch.setitem(
        sys.modules,
        "tokenizers",
        SimpleNamespace(Tokenizer=SimpleNamespace(from_file=lambda path: CharacterTokenizer())),
    )
    raw = MultilingualEncoder(tmp_path, preprocessing="raw")
    normalized = MultilingualEncoder(tmp_path)
    assert "preprocessing" not in raw.metadata
    assert normalized.metadata["preprocessing"] == "nfkc-no-tatweel-bidi-v1"
    assert raw.metadata == {
        key: value for key, value in normalized.metadata.items() if key != "preprocessing"
    }


def test_unknown_preprocessing_is_rejected_before_model_loading(tmp_path):
    with pytest.raises(ValueError, match="raw ou normalized"):
        MultilingualEncoder(tmp_path, preprocessing="unknown")


def test_normalized_chunk_offsets_keep_original_tatweel_and_unicode(encoder):
    text = "\u202b  والــي بنــك المغــرب \ufefb \ufb01 e\u0301 \u00ad\u202c " * 20
    spans = encoder.split_offsets(text, max_tokens=20, overlap=5)
    assert spans[0][0] == 0 and spans[-1][1] == len(text)
    assert all(start < end for start, end in spans)
    assert any("ــ" in text[start:end] for start, end in spans)
    assert all(
        len(encoder._tokenizer.encode(normalize_model_text(text[start:end])).ids) <= 128
        for start, end in spans
    )


def test_snapshot_checksum_and_revision(tmp_path):
    encoder = MultilingualEncoder.__new__(MultilingualEncoder)
    encoder.model_dir = tmp_path
    for name in MODEL_FILES:
        (tmp_path / name).write_bytes(name.encode())
    manifest = {
        "repository": MODEL_REPOSITORY,
        "revision": MODEL_REVISION,
        "files_sha256": {name: _sha256(tmp_path / name) for name in MODEL_FILES},
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    assert encoder._verify_snapshot()["revision"] == MODEL_REVISION
    (tmp_path / "tokenizer.json").write_bytes(b"changed")
    with pytest.raises(RuntimeError, match="Intégrité"):
        encoder._verify_snapshot()
    manifest["revision"] = "wrong"
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(RuntimeError, match="révision fixée"):
        encoder._verify_snapshot()


@pytest.mark.skipif(
    os.environ.get("RAG_RUN_MODEL_TESTS") != "1", reason="Explicit local-model check"
)
def test_prepared_real_model_french_arabic_and_exact_offsets():
    root = Path(os.environ.get("RAG_DATA_DIR", "data"))
    encoder = MultilingualEncoder(root / "models", allow_download=False)
    texts = ["Les banques doivent obtenir un agrément.", "يجب على البنوك الحصول على ترخيص."]
    vectors = encoder.encode_documents(texts)
    assert vectors.shape == (2, 384)
    assert np.isfinite(vectors).all()
    np.testing.assert_allclose(np.linalg.norm(vectors, axis=1), 1, atol=1e-5)
    long_text = (texts[0] + " " + texts[1] + " ") * 60
    spans = encoder.split_offsets(long_text)
    assert len(spans) > 2
    assert spans[0][0] == 0 and spans[-1][1] == len(long_text)
    assert all(start < end for start, end in spans)
    assert encoder.encode_documents([long_text[start:end] for start, end in spans]).shape[1] == 384
    tatweel_text = "\u202bوالــي بنــك المغــرب\u202c \ufefb \ufb01 e\u0301 \u00ad " * 60
    tatweel_spans = encoder.split_offsets(tatweel_text)
    assert tatweel_spans[0][0] == 0 and tatweel_spans[-1][1] == len(tatweel_text)
    assert all(
        len(encoder._tokenizer.encode(normalize_model_text(tatweel_text[start:end])).ids) <= 128
        for start, end in tatweel_spans
    )
    assert encoder.encode_documents(
        [tatweel_text[start:end] for start, end in tatweel_spans]
    ).shape == (len(tatweel_spans), 384)
    assert encoder.metadata["preprocessing"] == "nfkc-no-tatweel-bidi-v1"
    raw_encoder = MultilingualEncoder(root / "models", preprocessing="raw")
    raw_spans = raw_encoder.split_offsets(tatweel_text)
    assert len(raw_spans) > len(tatweel_spans)
    assert "preprocessing" not in raw_encoder.metadata
    assert raw_encoder.encode_documents(
        [tatweel_text[start:end] for start, end in raw_spans]
    ).shape == (len(raw_spans), 384)
