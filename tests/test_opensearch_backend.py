"""OpenSearch request/contract tests with an in-memory client double.

These tests do not claim to validate a running OpenSearch service.
"""

from types import SimpleNamespace

import numpy as np
import pytest

from rag_reglementation_maroc.models import Article, Chunk
from rag_reglementation_maroc.opensearch_backend import OpenSearchRetriever, _fuse


def article(number="1", language="fr"):
    source = f"bam-10312-{language}"
    return Article(
        id=f"{source}:article-{number}",
        document_id=f"{source}-2022-03-31",
        source_id=source,
        article_id=number,
        language=language,
        title=f"Article {number}",
        text=f"Les banques sont soumises à agrément. Article {number}.",
        source_url="https://www.bkam.ma/official.pdf",
        page_start=1,
        page_end=1,
        version_date="2022-03-31",
        sha256="a" * 64,
    )


def chunk(source, suffix="0"):
    return Chunk(
        id=f"{source.id}:chunk-{suffix}",
        article_ref=source.id,
        text=source.text,
        char_start=0,
        char_end=len(source.text),
    )


class FakeClient:
    def __init__(self):
        self.mapping = None
        self.creations = []
        self.bulks = []
        self.searches = []
        self.responses = []
        self.indices = SimpleNamespace(
            exists=lambda index: self.mapping is not None,
            create=self.create,
            get_mapping=lambda index: {index: {"mappings": self.mapping or {}}},
        )

    def create(self, index, body):
        self.creations.append(body)
        self.mapping = body["mappings"]

    def bulk(self, body, refresh):
        self.bulks.append(body)
        return {"errors": False}

    def search(self, index, body):
        self.searches.append(body)
        return {"hits": {"hits": self.responses.pop(0)}}


class FakeEncoder:
    metadata = {"model": "test-double", "revision": "unit-test", "dimension": 384}

    def encode_documents(self, documents):
        return np.tile(self.encode_query(""), (len(documents), 1))

    def encode_query(self, question):
        vector = np.zeros(384, dtype=np.float32)
        vector[0] = 1
        return vector


def hit(passage, score, vector=False):
    source = {"text": passage.text, "article_ref": passage.article_ref}
    if vector:
        source["embedding"] = FakeEncoder().encode_query("").tolist()
    return {"_id": passage.id, "_score": score, "_source": source}


def make_retriever(neural=False):
    articles = [article("1"), article("2")]
    chunks = [chunk(source) for source in articles]
    client = FakeClient()
    retriever = OpenSearchRetriever(
        articles, chunks, FakeEncoder() if neural else None, client=client
    )
    client.mapping = {"_meta": {"fingerprint": retriever.fingerprint}}
    return retriever, client, chunks


def test_constructor_never_indexes_and_explicit_index_is_idempotent():
    source = article()
    client = FakeClient()
    retriever = OpenSearchRetriever([source], [chunk(source)], client=client)
    assert client.creations == [] and client.bulks == []
    assert retriever.index()["chunks"] == 1
    retriever.index()
    assert len(client.creations) == 1 and len(client.bulks) == 2
    assert client.creations[0]["settings"]["index"]["knn"] is False


def test_index_with_neural_vectors_and_model_provenance():
    source = article()
    client = FakeClient()
    retriever = OpenSearchRetriever([source], [chunk(source)], FakeEncoder(), client=client)
    retriever.index()
    assert client.creations[0]["mappings"]["properties"]["embedding"]["dimension"] == 384
    assert len(client.bulks[0][1]["embedding"]) == 384
    assert retriever.metadata["encoder"]["model"] == "test-double"


def test_index_mismatch_is_rejected_without_overwriting():
    retriever, client, _ = make_retriever()
    client.mapping["_meta"]["fingerprint"] = "other-corpus"
    with pytest.raises(RuntimeError, match="corpus/modèle"):
        retriever.index()
    assert client.bulks == [] and client.creations == []


def test_bm25_preserves_original_evidence_and_filters_language():
    retriever, client, chunks = make_retriever()
    client.responses = [[hit(chunks[0], 3.5)]]
    result = retriever.search("agrément", language="fr")
    assert result[0].chunk.text == result[0].article.text
    assert result[0].lexical_score == 3.5
    assert result[0].semantic_score is None
    assert result[0].ranks == {"bm25": 1}
    assert client.searches[0]["query"]["bool"]["filter"] == [{"term": {"language": "fr"}}]


def test_hybrid_fuses_ranks_and_returns_actual_cosine():
    retriever, client, chunks = make_retriever(neural=True)
    client.responses = [
        [hit(chunks[0], 5), hit(chunks[1], 2)],
        [hit(chunks[1], 9, vector=True), hit(chunks[0], 8, vector=True)],
    ]
    result = retriever.search("banques", mode="hybrid", language="fr")
    assert len(result) == 2
    assert result[0].score == pytest.approx(1 / 61 + 1 / 62)
    assert result[0].semantic_score == pytest.approx(1.0)
    assert set(result[0].ranks) == {"bm25", "semantic"}
    assert client.searches[1]["query"]["knn"]["embedding"]["filter"] == {"term": {"language": "fr"}}


def test_multiple_passages_of_one_article_are_deduplicated():
    source = article()
    chunks = [chunk(source, "0"), chunk(source, "1")]
    client = FakeClient()
    retriever = OpenSearchRetriever([source], chunks, client=client)
    client.mapping = {"_meta": {"fingerprint": retriever.fingerprint}}
    client.responses = [[hit(chunks[0], 4), hit(chunks[1], 2)]]
    assert len(retriever.search("banques")) == 1


def test_modified_evidence_is_rejected():
    retriever, client, chunks = make_retriever()
    response = hit(chunks[0], 4)
    response["_source"]["text"] = "Texte modifié dans le cluster."
    client.responses = [[response]]
    with pytest.raises(RuntimeError, match="diffère"):
        retriever.search("banques")


def test_explicit_article_filter_and_absent_article():
    retriever, client, chunks = make_retriever()
    client.responses = [[hit(chunks[1], 0)]]
    result = retriever.search("Que prévoit l'article 2 ?", language="fr")
    assert result[0].article.article_id == "2"
    query = client.searches[0]["query"]["bool"]
    assert query["minimum_should_match"] == 0
    assert {"term": {"article_id": "2"}} in query["filter"]
    assert retriever.search("Que prévoit l'article 999 ?") == []


@pytest.mark.parametrize(
    "question",
    ["Que disent les articles 151 et 155 ?", "ما نص المادتين ١٥١ و١٥٥ ؟"],
)
def test_joint_article_references_keep_both_ids_in_lexical_and_neural_filters(question):
    articles = [article("151"), article("155"), article("154")]
    chunks = [chunk(source) for source in articles]
    client = FakeClient()
    retriever = OpenSearchRetriever(articles, chunks, FakeEncoder(), client=client)
    client.mapping = {"_meta": {"fingerprint": retriever.fingerprint}}
    client.responses = [
        [hit(chunks[0], 4), hit(chunks[1], 2)],
        [hit(chunks[1], 9, vector=True), hit(chunks[0], 8, vector=True)],
    ]
    result = retriever.search(question, language="fr", mode="hybrid")
    assert {item.article.article_id for item in result} == {"151", "155"}
    expected = {"terms": {"article_id": ["151", "155"]}}
    assert expected in client.searches[0]["query"]["bool"]["filter"]
    assert expected in client.searches[1]["query"]["knn"]["embedding"]["filter"]["bool"]["filter"]


@pytest.mark.parametrize(
    "kwargs",
    [{"mode": "semantic"}, {"mode": "unknown"}, {"language": "en"}, {"top_k": 0}, {"top_k": 101}],
)
def test_invalid_search_or_neural_without_encoder(kwargs):
    retriever, _, _ = make_retriever()
    with pytest.raises(ValueError):
        retriever.search("banques", **kwargs)


def test_chunk_offsets_must_match_original():
    source = article()
    passage = chunk(source).model_copy(update={"text": "Texte incorrect"})
    with pytest.raises(ValueError, match="exactement"):
        OpenSearchRetriever([source], [passage], client=FakeClient())


def test_rrf_counts_a_repeated_candidate_once_per_list():
    result = _fuse({"bm25": ["a", "a", "b"], "semantic": ["b", "a"]})
    assert result["a"] == pytest.approx(1 / 61 + 1 / 62)
    assert result["a"] == result["b"]


def test_service_errors_are_safe_runtime_errors():
    retriever, client, _ = make_retriever()

    def unavailable(**kwargs):
        raise ConnectionError("Private transport details")

    client.indices.get_mapping = unavailable
    with pytest.raises(RuntimeError, match="OpenSearch indisponible") as error:
        retriever.search("agrément")
    assert "Private transport details" not in str(error.value)


def test_readiness_only_reads_existing_index():
    retriever, client, _ = make_retriever()
    assert retriever.check_ready() is None
    assert client.creations == [] and client.bulks == [] and client.searches == []


def test_readiness_fails_when_service_is_unavailable():
    retriever, client, _ = make_retriever()

    def unavailable(**kwargs):
        raise ConnectionError("Private connection details")

    client.indices.get_mapping = unavailable
    with pytest.raises(RuntimeError, match="OpenSearch indisponible"):
        retriever.check_ready()
    assert client.creations == [] and client.bulks == []
