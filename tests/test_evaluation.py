"""Pure fixtures: these checks do not measure banking-corpus performance."""

import copy
import json
from pathlib import Path

import pytest

from rag_reglementation_maroc.evaluation import evaluate_retrieval, load_cases
from rag_reglementation_maroc.models import Article, Chunk, SearchHit


def make_hit(article_id, language="fr"):
    text = f"Synthetic fixture for article {article_id}."
    article = Article(
        id=f"fixture-{language}:article-{article_id}",
        document_id="fixture",
        source_id=f"fixture-{language}",
        article_id=article_id,
        language=language,
        title="Synthetic fixture",
        text=text,
        source_url="https://example.org/fixture.pdf",
        page_start=1,
        page_end=1,
        version_date="2022-03-31",
        sha256="a" * 64,
    )
    chunk = Chunk(
        id=f"{article.id}:chunk-0",
        article_ref=article.id,
        text=text,
        char_start=0,
        char_end=len(text),
    )
    return SearchHit(chunk=chunk, article=article, score=1.0)


def make_case(case_id="q1", expected=None, answerable=True):
    return {
        "id": case_id,
        "group_id": case_id,
        "split": "dev",
        "question": case_id,
        "query_language": "fr",
        "source_language": "fr",
        "answerable": answerable,
        "expected_article_ids": ["34"] if expected is None and answerable else (expected or []),
    }


class FakeRetriever:
    def __init__(self, hits):
        self.hits = hits
        self.calls = []

    def search(self, question, language=None, mode="bm25", top_k=5):
        self.calls.append((question, language, mode, top_k))
        return self.hits.get(question, [])


def test_article_deduplication_and_reciprocal_rank():
    hits = [make_hit("10"), make_hit("10"), make_hit("34")]
    retriever = FakeRetriever({"q1": hits})
    result = evaluate_retrieval(retriever, [make_case()], "bm25", top_k=3)
    row = result["rows"][0]
    assert row["retrieved_article_ids"] == ["10", "34"]
    assert row["recall_at_k"] == 1.0
    assert row["reciprocal_rank_at_k"] == 0.5
    assert retriever.calls == [("q1", "fr", "bm25", 3)]
    assert result["metadata"]["faithfulness_evaluated"] is False
    assert result["metadata"]["abstention_evaluated"] is False


def test_multiple_gold_articles_have_fractional_recall():
    result = evaluate_retrieval(
        FakeRetriever({"q1": [make_hit("34")]}),
        [make_case(expected=["34", "35"])],
        "hybrid",
        top_k=1,
    )
    assert result["rows"][0]["recall_at_k"] == 0.5
    assert result["rows"][0]["reciprocal_rank_at_k"] == 1.0


def test_negatives_do_not_inflate_positive_retrieval_metrics():
    cases = [make_case(), make_case("negative", answerable=False)]
    result = evaluate_retrieval(FakeRetriever({}), cases, "bm25")
    overall = next(item for item in result["aggregate"] if item["direction"] == "overall")
    assert overall["n_positive"] == 1
    assert overall["n_negative"] == 1
    assert overall["recall_at_5"] == 0
    assert result["rows"][1]["recall_at_k"] is None
    assert overall["negative_abstention_rate"] is None


def test_callback_answerability_is_measured_separately():
    cases = [
        make_case("yes"),
        make_case("no"),
        make_case("false_positive", answerable=False),
        make_case("true_negative", answerable=False),
    ]
    result = evaluate_retrieval(
        FakeRetriever({}),
        cases,
        "semantic",
        decide_answer=lambda question, hits, mode: question in {"yes", "false_positive"},
    )
    overall = next(item for item in result["aggregate"] if item["direction"] == "overall")
    assert overall["coverage"] == 0.5
    assert overall["positive_answer_rate"] == 0.5
    assert overall["negative_abstention_rate"] == 0.5
    assert overall["answerability_precision"] == 0.5
    assert overall["answerability_balanced_accuracy"] == 0.5
    assert overall["recall_at_5"] == 0


def test_wrong_source_language_is_an_error():
    with pytest.raises(ValueError, match="language"):
        evaluate_retrieval(FakeRetriever({"q1": [make_hit("34", "ar")]}), [make_case()], "bm25")


def test_macro_is_mean_of_directions_not_query_weighted():
    cases = [make_case("q1"), make_case("q2"), make_case("q3")]
    cases[2]["query_language"] = "ar"
    result = evaluate_retrieval(
        FakeRetriever({"q1": [make_hit("34")], "q2": [make_hit("34")]}), cases, "bm25"
    )
    overall = next(item for item in result["aggregate"] if item["direction"] == "overall")
    macro = next(item for item in result["aggregate"] if item["direction"] == "macro_direction")
    assert overall["recall_at_5"] == pytest.approx(2 / 3)
    assert macro["recall_at_5"] == 0.5


def test_case_fingerprint_is_deterministic():
    retriever = FakeRetriever({})
    a = evaluate_retrieval(retriever, [make_case()], "bm25")
    b = evaluate_retrieval(retriever, [make_case()], "bm25")
    assert a["metadata"]["cases_sha256"] == b["metadata"]["cases_sha256"]


def test_load_validates_groups_before_split_selection(tmp_path):
    case = make_case()
    second = copy.deepcopy(case)
    second.update(id="translation", split="test", query_language="ar")
    path = tmp_path / "cases.json"
    path.write_text(json.dumps([case, second]), encoding="utf-8")
    with pytest.raises(ValueError, match="cannot cross"):
        load_cases(path, split="dev")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", ""),
        ("answerable", "yes"),
        ("expected_article_ids", []),
        ("expected_article_ids", ["34", "34"]),
        ("expected_article_ids", [34]),
        ("query_language", "en"),
        ("question", " "),
        ("split", "development"),
    ],
)
def test_invalid_cases_are_rejected(tmp_path, field, value):
    case = make_case()
    case[field] = value
    path = tmp_path / "cases.json"
    path.write_text(json.dumps([case]), encoding="utf-8")
    with pytest.raises(ValueError):
        load_cases(path)


@pytest.mark.parametrize("top_k", [0, -1, 1.5, True])
def test_invalid_cutoff_is_rejected(top_k):
    with pytest.raises(ValueError, match="positive integer"):
        evaluate_retrieval(FakeRetriever({}), [make_case()], "bm25", top_k=top_k)


def test_pilot_benchmark_has_grouped_translations():
    path = Path(__file__).resolve().parents[1] / "evaluation" / "questions.json"
    cases = load_cases(path)
    assert len(cases) == 64
    for group in {case["group_id"] for case in cases}:
        variants = [case for case in cases if case["group_id"] == group]
        assert len(variants) == 4
        assert len({case["split"] for case in variants}) == 1
        assert {(case["query_language"], case["source_language"]) for case in variants} == {
            ("fr", "fr"),
            ("fr", "ar"),
            ("ar", "fr"),
            ("ar", "ar"),
        }
    for split in ("dev", "test"):
        selected = load_cases(path, split)
        assert len(selected) == 32
        assert sum(case["answerable"] for case in selected) == 20
