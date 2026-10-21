"""Explicitly prepared, revision-pinned multilingual embeddings.

Importing this module never imports FastEmbed, downloads a model or opens a
network connection. Only ``allow_download=True`` permits preparation.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from difflib import SequenceMatcher
from importlib.metadata import version
from pathlib import Path

import numpy as np

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MODEL_REPOSITORY = "Qdrant/paraphrase-multilingual-MiniLM-L12-v2-onnx-Q"
MODEL_REVISION = "faf4aa4225822f3bc6376869cb1164e8e3feedd0"
MODEL_FILES = (
    "config.json",
    "model_optimized.onnx",
    "special_tokens_map.json",
    "tokenizer.json",
    "tokenizer_config.json",
)
DIMENSION = 384
MODEL_TOKEN_LIMIT = 128
PREPROCESSING = "nfkc-no-tatweel-bidi-v1"


def _normalized_with_offsets(text: str) -> tuple[str, list[tuple[int, int]]]:
    """Normalize model input while retaining each character's original span.

    Per-character NFKC expands PDF presentation forms/ligatures. A second NFKC
    pass composes sequences such as ``e`` plus an accent; alignment maps those
    replacements to the full original span. Source/evidence text is untouched.
    """
    characters = []
    original_spans = []
    for position, original in enumerate(text):
        for character in unicodedata.normalize("NFKC", original):
            if character == "\u0640" or unicodedata.category(character) == "Cf":
                continue
            characters.append(character)
            original_spans.append((position, position + 1))
    expanded = "".join(characters)
    normalized = unicodedata.normalize("NFKC", expanded)
    if normalized == expanded:
        return normalized, original_spans
    aligned_spans = []
    for operation, start, end, target_start, target_end in SequenceMatcher(
        a=expanded, b=normalized, autojunk=False
    ).get_opcodes():
        if operation == "equal":
            aligned_spans.extend(original_spans[start:end])
        elif operation in ("replace", "insert"):
            source = original_spans[start:end] or original_spans[max(0, start - 1) : start + 1]
            if source:
                span = (source[0][0], source[-1][1])
                aligned_spans.extend([span] * (target_end - target_start))
    if len(aligned_spans) != len(normalized):
        raise RuntimeError("Impossible de relier le texte normalisé au texte original.")
    return normalized, aligned_spans


def normalize_model_text(text: str) -> str:
    return _normalized_with_offsets(text)[0]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class MultilingualEncoder:
    """Load a local ONNX snapshot, preparing it only on explicit request.

    The quantized model is about 220 MB. Its tokenizer truncates at 128 tokens,
    so inputs exceeding that limit are rejected rather than silently shortened.
    ``split_offsets`` uses the exact snapshot tokenizer and preserves original
    character offsets for evidence, including Arabic and accented French.
    """

    def __init__(
        self, cache_dir: Path, allow_download: bool = False, preprocessing: str = "normalized"
    ) -> None:
        if preprocessing not in ("raw", "normalized"):
            raise ValueError("preprocessing doit valoir raw ou normalized.")
        self.preprocessing = preprocessing
        self.cache_dir = Path(cache_dir)
        self.model_dir = self.cache_dir / MODEL_REVISION
        if allow_download:
            self._prepare_snapshot()
        manifest = self._verify_snapshot()
        try:
            from fastembed import TextEmbedding
            from tokenizers import Tokenizer
        except ImportError as exc:
            raise RuntimeError("Installer l'option neural : pip install '.[neural]'.") from exc

        # This separate tokenizer has no truncation or padding. FastEmbed keeps
        # its own inference tokenizer, configured by the same pinned snapshot.
        self._tokenizer = Tokenizer.from_file(str(self.model_dir / "tokenizer.json"))
        self._tokenizer.no_truncation()
        self._tokenizer.no_padding()
        self._model = TextEmbedding(
            model_name=MODEL_NAME,
            cache_dir=str(self.cache_dir),
            specific_model_path=str(self.model_dir),
            local_files_only=True,
            providers=["CPUExecutionProvider"],
            threads=2,
        )
        self._metadata = {
            "model": MODEL_NAME,
            "repository": MODEL_REPOSITORY,
            "revision": MODEL_REVISION,
            "dimension": DIMENSION,
            "token_limit": MODEL_TOKEN_LIMIT,
            "default_chunk_tokens": 110,
            "license": "Apache-2.0",
            "fastembed_version": version("fastembed"),
            "files_sha256": manifest["files_sha256"],
        }
        # Absence of this key reproduces the V1 model/cache signature exactly.
        if preprocessing == "normalized":
            self._metadata["preprocessing"] = PREPROCESSING

    def _prepare_text(self, text: str) -> tuple[str, list[tuple[int, int]]]:
        if self.preprocessing == "raw":
            return text, [(position, position + 1) for position in range(len(text))]
        return _normalized_with_offsets(text)

    def _prepare_snapshot(self) -> None:
        try:
            from huggingface_hub import snapshot_download
        except ImportError as exc:
            raise RuntimeError("Installer l'option neural avant prepare-model.") from exc
        self.model_dir.mkdir(parents=True, exist_ok=True)
        snapshot_download(
            repo_id=MODEL_REPOSITORY,
            revision=MODEL_REVISION,
            local_dir=self.model_dir,
            allow_patterns=list(MODEL_FILES),
        )
        missing = [name for name in MODEL_FILES if not (self.model_dir / name).is_file()]
        if missing:
            raise RuntimeError(f"Le snapshot est incomplet : {', '.join(missing)}")
        manifest = {
            "repository": MODEL_REPOSITORY,
            "revision": MODEL_REVISION,
            "files_sha256": {name: _sha256(self.model_dir / name) for name in MODEL_FILES},
        }
        (self.model_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    def _verify_snapshot(self) -> dict:
        path = self.model_dir / "manifest.json"
        if not path.is_file():
            raise RuntimeError(
                "Modèle local absent. Exécuter explicitement prepare-model avant "
                "d'activer RAG_ENCODER=multilingual ; aucun téléchargement automatique."
            )
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("Manifeste de modèle invalide ; relancer prepare-model.") from exc
        if (
            manifest.get("repository") != MODEL_REPOSITORY
            or manifest.get("revision") != MODEL_REVISION
        ):
            raise RuntimeError("Le modèle local ne correspond pas à la révision fixée.")
        expected = manifest.get("files_sha256", {})
        for name in MODEL_FILES:
            file_path = self.model_dir / name
            if not file_path.is_file() or expected.get(name) != _sha256(file_path):
                raise RuntimeError(f"Intégrité du modèle invalide : {name}.")
        return manifest

    @property
    def metadata(self) -> dict:
        # Return fresh nested data so callers cannot mutate model provenance.
        return json.loads(json.dumps(self._metadata))

    def split_offsets(
        self, text: str, max_tokens: int = 110, overlap: int = 20
    ) -> list[tuple[int, int]]:
        if not 1 <= max_tokens <= MODEL_TOKEN_LIMIT - 2:
            raise ValueError("max_tokens doit être compris entre 1 et 126.")
        if not 0 <= overlap < max_tokens:
            raise ValueError("overlap doit être positif et inférieur à max_tokens.")
        if not text:
            return []
        normalized, original_spans = self._prepare_text(text)
        encoding = self._tokenizer.encode(normalized, add_special_tokens=False)
        offsets = [
            (original_spans[start][0], original_spans[end - 1][1])
            for start, end in encoding.offsets
            if end > start
        ]
        if not offsets:
            return [(0, len(text))]
        spans = []
        step = max_tokens - overlap
        for token_start in range(0, len(offsets), step):
            token_end = min(token_start + max_tokens, len(offsets))
            start = 0 if token_start == 0 else offsets[token_start][0]
            end = len(text) if token_end == len(offsets) else offsets[token_end - 1][1]
            if end > start and (not spans or spans[-1] != (start, end)):
                spans.append((start, end))
            if token_end == len(offsets):
                break
        return spans

    def encode_documents(self, documents: list[str]) -> np.ndarray:
        if not documents:
            return np.empty((0, DIMENSION), dtype=np.float32)
        normalized_documents = [self._prepare_text(text)[0] for text in documents]
        for text in normalized_documents:
            if not text.strip():
                raise ValueError("Un texte à encoder ne peut pas être vide.")
            if len(self._tokenizer.encode(text).ids) > MODEL_TOKEN_LIMIT:
                raise ValueError(
                    "Le texte dépasse les 128 tokens du modèle. Utiliser split_offsets "
                    "pour les documents ou raccourcir la question."
                )
        vectors = np.asarray(
            list(self._model.embed(normalized_documents, batch_size=32)), dtype=np.float32
        )
        if vectors.shape != (len(documents), DIMENSION) or not np.isfinite(vectors).all():
            raise RuntimeError("L'encodeur n'a pas produit les vecteurs attendus.")
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        if (norms <= 0).any():
            raise RuntimeError("L'encodeur a produit un vecteur nul.")
        return vectors / norms

    def encode_query(self, question: str) -> np.ndarray:
        return self.encode_documents([question])[0]
