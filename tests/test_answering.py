"""Un modèle ne peut inventer ni identifiant ni extrait de source."""

import json

import httpx
import pytest

from rag_reglementation_maroc.answering import (
    AbstentionPolicy,
    AnswerService,
    GeneratedAnswer,
    OllamaClient,
)


def test_extractive_quotes_are_exact_and_current_law_is_out_of_scope(retriever):
    service = AnswerService(retriever)
    result = service.ask("article 34", source_language="fr")
    assert result["status"] == "evidence_found"
    assert result["citations"][0]["quote"] in retriever.articles["synthetic-fr:article-34"].text
    assert result["semantic_faithfulness"] == "not_evaluated"
    refused = service.ask("Quel est l'agrément actuellement en vigueur ?", source_language="fr")
    assert refused["status"] == "abstained"
    assert refused["reason"] == "edition_does_not_establish_current_law"


@pytest.mark.parametrize("question", ["article 999", "xyzzqvunrelated", "ما القاعدة الحالية؟"])
def test_missing_or_current_evidence_is_not_answered(retriever, question):
    assert AnswerService(retriever).ask(question)["status"] == "abstained"


def test_schema_distinguishes_abstention_from_claims():
    with pytest.raises(ValueError):
        GeneratedAnswer.model_validate({"abstain": False, "claims": []})


def model_returning(payload):
    def handler(request):
        sent = json.loads(request.content)
        assert sent["stream"] is False
        assert sent["options"]["temperature"] == 0
        return httpx.Response(200, json={"message": {"content": json.dumps(payload)}})

    return OllamaClient(client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_ollama_structured_response_with_known_source_is_accepted(retriever):
    hit = retriever.search("article 34", language="fr")[0]
    model = model_returning(
        {
            "abstain": False,
            "claims": [
                {
                    "text": "Une autorité accorde l'agrément.",
                    "citation_id": hit.chunk.id,
                    "quote": hit.chunk.text,
                },
            ],
        }
    )
    result = AnswerService(retriever, ollama=model).ask(
        "article 34",
        source_language="fr",
        generator="ollama",
    )
    assert result["status"] == "evidence_found"
    assert result["citations"][0]["article_id"] == "34"
    assert result["semantic_faithfulness"] == "not_evaluated"


@pytest.mark.parametrize(
    "field,value",
    [
        ("citation_id", "invented-source"),
        ("quote", "Cet extrait inventé ne figure pas dans le passage."),
    ],
)
def test_invented_evidence_fails_closed(retriever, field, value):
    hit = retriever.search("article 34", language="fr")[0]
    claim = {
        "text": "Une autorité accorde l'agrément.",
        "citation_id": hit.chunk.id,
        "quote": hit.chunk.text,
    }
    claim[field] = value
    service = AnswerService(
        retriever, ollama=model_returning({"abstain": False, "claims": [claim]})
    )
    result = service.ask("article 34", source_language="fr", generator="ollama")
    assert result["status"] == "abstained"
    assert result["citations"] == []
    assert result["reason"] == "invalid_generated_citation_or_schema"


def test_policy_rejects_invalid_thresholds():
    with pytest.raises(ValueError):
        AbstentionPolicy(semantic_threshold=1.2)


def test_contractual_is_not_a_temporal_request(retriever):
    from rag_reglementation_maroc.answering import temporal_scope_conflict

    assert not temporal_scope_conflict("Quelles sont les conditions contractuelles ?")
    assert temporal_scope_conflict("Quelle règle est actuellement applicable ?")
    result = AnswerService(retriever).ask(
        "Quel est le prix d'un billet de train selon l'article 34 ?",
        source_language="fr",
    )
    assert result["status"] == "abstained"


def test_multi_article_lookup_and_neighboring_evidence(articles):
    from rag_reglementation_maroc.retrieval import LocalRetriever
    from rag_reglementation_maroc.text import detect_language

    service = AnswerService(LocalRetriever(articles))
    result = service.ask("Que disent les articles 34 et 155 ?", source_language="fr")
    assert result["status"] == "evidence_found"
    assert {item["article_id"] for item in result["citations"]} == {"34", "155"}
    assert detect_language("Quel est le contenu de l'article ١٥٥ ?") == "fr"
    long_text = ("Procédure de paiement et transferts. " * 28) + "Le chèque est exclu."
    article = articles[0].model_copy(update={"text": long_text})
    long_service = AnswerService(LocalRetriever([article]))
    answer = long_service.ask("article 34", source_language="fr")
    assert any("chèque est exclu" in item["quote"] for item in answer["citations"])


def test_context_keeps_five_anchors_before_neighbours_of_long_articles(articles):
    from rag_reglementation_maroc.models import SearchHit
    from rag_reglementation_maroc.retrieval import LocalRetriever

    documents = []
    for number in range(1, 6):
        repetitions = 150 if number <= 2 else 35
        documents.append(
            articles[0].model_copy(
                update={
                    "id": f"synthetic-fr:article-{number}",
                    "article_id": str(number),
                    "text": (
                        f"Document synthétique numéro {number}, paragraphe de contexte. "
                        * repetitions
                    ),
                }
            )
        )
    retriever = LocalRetriever(documents)
    anchors = []
    for rank, article in enumerate(documents, start=1):
        siblings = [chunk for chunk in retriever.chunks if chunk.article_ref == article.id]
        anchors.append(
            SearchHit(
                chunk=siblings[2] if rank <= 2 else siblings[0],
                article=article,
                score=1 / rank,
                ranks={"bm25": rank},
            )
        )
    context = AnswerService(retriever).expand_evidence(anchors)
    assert [hit.chunk.id for hit in context[:5]] == [hit.chunk.id for hit in anchors]
    assert len(context) == 12
    assert len({hit.chunk.id for hit in context}) == 12
    assert {hit.article.id for hit in context} == {article.id for article in documents}
    for hit in context:
        assert hit.chunk.text == hit.article.text[hit.chunk.char_start : hit.chunk.char_end]


def test_provider_statistics_and_structured_generation_stay_local(retriever):
    hit = retriever.search("article 34", language="fr")[0]
    generation = {
        "abstain": False,
        "claims": [
            {
                "text": "Une autorité accorde l'agrément.",
                "citation_id": hit.chunk.id,
                "quote": hit.chunk.text,
            }
        ],
    }
    stats = {
        "prompt_eval_count": 1700,
        "eval_count": 90,
        "total_duration": 123000,
        "done_reason": "stop",
        "load_duration": 45000,
    }

    def handler(request):
        return httpx.Response(
            200,
            json={
                "message": {"content": json.dumps(generation)},
                **stats,
                "ignored_provider_field": "not part of the public contract",
            },
        )

    model = OllamaClient(client=httpx.Client(transport=httpx.MockTransport(handler)))
    result = AnswerService(retriever, ollama=model).ask(
        "article 34",
        source_language="fr",
        generator="ollama",
    )
    assert result["status"] == "evidence_found"
    assert model.last_stats == stats
    assert model.last_generation["parsed"] == generation
    assert model.last_generation["schema_valid"] is True
    assert "provider_stats" not in result and "provider_generation" not in result
    assert "last_stats" not in result and "last_generation" not in result


def test_truncated_provider_output_remains_available_for_local_diagnostics(retriever):
    content = '{"abstain":false,"claims":['

    def handler(request):
        return httpx.Response(
            200,
            json={
                "message": {"content": content},
                "done_reason": "length",
                "eval_count": 900,
            },
        )

    model = OllamaClient(client=httpx.Client(transport=httpx.MockTransport(handler)))
    result = AnswerService(retriever, ollama=model).ask(
        "article 34",
        source_language="fr",
        generator="ollama",
    )
    assert result["status"] == "abstained"
    assert result["reason"] == "invalid_generated_citation_or_schema"
    assert model.last_stats["done_reason"] == "length"
    assert model.last_stats["eval_count"] == 900
    assert model.last_generation == {
        "raw_content": content,
        "parsed": None,
        "schema_valid": False,
    }


def test_failed_provider_request_clears_previous_diagnostics():
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(
                200,
                json={
                    "message": {"content": '{"abstain":true,"claims":[]}'},
                    "eval_count": 9,
                },
            )
        return httpx.Response(503)

    model = OllamaClient(client=httpx.Client(transport=httpx.MockTransport(handler)))
    model.generate("Question synthétique", [], "fr")
    assert model.last_stats["eval_count"] == 9
    with pytest.raises(httpx.HTTPStatusError):
        model.generate("Autre question synthétique", [], "fr")
    assert model.last_stats == {} and model.last_generation is None


def test_context_adds_article_introductions_when_anchors_are_at_the_end(articles):
    from rag_reglementation_maroc.models import SearchHit
    from rag_reglementation_maroc.retrieval import LocalRetriever

    documents = [
        articles[0].model_copy(
            update={
                "id": f"synthetic-fr:article-{number}",
                "article_id": str(number),
                "text": "Autorité compétente mentionnée dans l'introduction. "
                + (f"Suite du document numéro {number}. " * 180),
            }
        )
        for number in range(1, 6)
    ]
    retriever = LocalRetriever(documents)
    anchors = []
    for rank, article in enumerate(documents, start=1):
        siblings = [chunk for chunk in retriever.chunks if chunk.article_ref == article.id]
        anchors.append(SearchHit(chunk=siblings[-1], article=article, score=1 / rank))
    context = AnswerService(retriever).expand_evidence(anchors)
    ids = {hit.chunk.id for hit in context}
    assert [hit.chunk.id for hit in context[:5]] == [hit.chunk.id for hit in anchors]
    assert len(context) <= 12
    for article in documents[:3]:
        siblings = [chunk for chunk in retriever.chunks if chunk.article_ref == article.id]
        assert {chunk.id for chunk in siblings[:2]} <= ids


def citation_hit(articles, text):
    from rag_reglementation_maroc.models import Chunk, SearchHit

    article = articles[0].model_copy(update={"text": text})
    chunk = Chunk(
        id=f"{article.id}:chunk-0",
        article_ref=article.id,
        text=text,
        char_start=0,
        char_end=len(text),
    )
    return SearchHit(chunk=chunk, article=article, score=1.0)


@pytest.mark.parametrize(
    "source,quoted,original",
    [
        (
            "يسند القرار إلى والــي بنــك المغــرب في هذا المثال.",
            "والي بنك المغرب",
            "والــي بنــك المغــرب",
        ),
        (
            "Le ﬁnancement exige une convention\n\t écrite dans ce cas.",
            "financement exige une convention écrite",
            "ﬁnancement exige une convention\n\t écrite",
        ),
        ("Le texte dit : ﻻ يجوز فعل ذلك في هذا المثال.", "لا يجوز فعل ذلك", "ﻻ يجوز فعل ذلك"),
        ("Une déci\u200esion écrite est requise.", "décision écrite", "déci\u200esion écrite"),
    ],
)
def test_typographically_equivalent_quote_returns_the_original_substring(
    articles,
    source,
    quoted,
    original,
):
    from rag_reglementation_maroc.answering import citation

    result = citation(citation_hit(articles, source), quoted)
    assert result["quote"] == original
    assert result["quote"] in source


@pytest.mark.parametrize(
    "quote",
    [
        "والي بنك المشرق",
        "محافظ بنك المغرب",
        "والي بنك المغرب دائما",
        "والي المصرف المغربي",
    ],
)
def test_typographic_matching_never_accepts_changed_letters_or_a_paraphrase(articles, quote):
    from rag_reglementation_maroc.answering import citation

    hit = citation_hit(articles, "يسند القرار إلى والــي بنــك المغــرب في هذا المثال.")
    with pytest.raises(ValueError, match="ne figure pas"):
        citation(hit, quote)


def test_partial_ligature_match_cannot_return_extra_letters(articles):
    from rag_reglementation_maroc.answering import citation

    hit = citation_hit(articles, "Le ﬂux monétaire est suivi.")
    with pytest.raises(ValueError, match="ne figure pas"):
        citation(hit, "lux monétaire")


def test_only_typographically_normalized_evidence_is_sent_to_the_model(articles):
    hit = citation_hit(articles, "Le ﬁnancement de والــي\u200e respecte le texte.")

    def handler(request):
        payload = json.loads(request.content)
        evidence = json.loads(payload["messages"][1]["content"])["evidence"]
        assert evidence[0]["passage"] == "Le financement de والي respecte le texte."
        assert "generic question" in payload["messages"][0]["content"]
        return httpx.Response(200, json={"message": {"content": '{"abstain":true,"claims":[]}'}})

    model = OllamaClient(client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert model.generate("Question synthétique", [hit], "fr").abstain
    assert "والــي" in hit.chunk.text and "ﬁnancement" in hit.chunk.text


def test_explicit_runtime_options_and_keep_alive_are_sent_without_changing_defaults():
    sent = []

    def handler(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={"message": {"content": '{"abstain":true,"claims":[]}'}})

    transport = httpx.MockTransport(handler)
    normal = OllamaClient(client=httpx.Client(transport=transport))
    normal.generate("Question synthétique", [], "fr")
    assert sent[0]["options"] == {"temperature": 0, "seed": 7, "num_ctx": 4096, "num_predict": 900}
    assert "keep_alive" not in sent[0]
    explicit = OllamaClient(
        client=httpx.Client(transport=transport),
        options={"num_ctx": 2048},
        keep_alive="15m",
        timeout=240,
    )
    explicit.generate("Question synthétique", [], "fr")
    assert sent[1]["options"]["num_ctx"] == 2048
    assert sent[1]["keep_alive"] == "15m"


def test_transport_timeout_is_preserved_as_local_diagnostic():
    def handler(request):
        raise httpx.ReadTimeout("Synthetic cold-load timeout", request=request)

    model = OllamaClient(client=httpx.Client(transport=httpx.MockTransport(handler)), timeout=180)
    with pytest.raises(httpx.ReadTimeout):
        model.generate("Question synthétique", [], "fr")
    assert model.last_error["exception"] == "ReadTimeout"
    assert model.last_error["stage"] == "http_request"
    assert model.last_error["timeout_seconds"] == 180
    assert model.last_generation is None


def test_transmitted_schema_generates_claims_before_the_abstention_decision():
    def handler(request):
        schema = json.loads(request.content)["format"]
        assert list(schema["properties"]) == ["claims", "abstain"]
        assert schema["required"] == ["claims", "abstain"]
        assert schema["additionalProperties"] is False
        assert schema["$defs"]["Claim"]["required"] == ["text", "citation_id", "quote"]
        return httpx.Response(200, json={"message": {"content": '{"claims":[],"abstain":true}'}})

    model = OllamaClient(client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert model.generate("Question synthétique", [], "fr").abstain
    with pytest.raises(ValueError):
        GeneratedAnswer.model_validate({"claims": [], "abstain": False})
