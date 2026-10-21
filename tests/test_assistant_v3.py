"""Contract and failure-mode tests; synthetic sources are not legal validation."""

import json

import pytest
from fastapi.testclient import TestClient

from rag_reglementation_assistant.corpus import _body, load_domain, sha
from rag_reglementation_assistant.evaluation import evaluate_development
from rag_reglementation_assistant.intent import parse
from rag_reglementation_assistant.service import AssistantService
from rag_reglementation_maroc.answering import AnswerService
from rag_reglementation_maroc.models import Article
from rag_reglementation_maroc.retrieval import LocalRetriever
from rag_reglementation_maroc.runtime import Settings
from rag_reglementation_ui.app import create_ui_app


def article(source, number, text, language="fr", document="circular-10-w-2016"):
    return Article(
        id=f"{source}:article-{number}",
        source_id=source,
        document_id=document,
        article_id=str(number),
        language=language,
        title="Synthetic",
        text=text,
        page_start=1,
        page_end=1,
        version_date="2023-12-31",
        sha256="a" * 64,
        source_url="https://www.bkam.ma/synthetic-test.pdf",
    )


@pytest.fixture
def assistant(tmp_path):
    base = [
        article(
            "test-law-fr", 157, "Dispositif interne adapté de réclamations.", document="law-103-12"
        ),
        article(
            "test-law-ar",
            157,
            "آلية داخلية ملائمة لمعالجة الشكايات.",
            language="ar",
            document="law-103-12",
        ),
    ]
    extra = [
        article(
            "bam-complaints-2023-fr",
            4,
            "Quarante jours ouvrés depuis la réception. Circonstances particulières : informer le client du nouveau délai.",
        ),
        article(
            "bam-complaints-2023-fr", 13, "Reporting trimestriel : le format est défini séparément."
        ),
        article(
            "bam-mediation-2023-fr",
            5,
            "Demande recevable : trente jours ouvrés. Prolongation : informer les parties.",
            document="circular-9-w-2016",
        ),
        article(
            "bam-mediation-2023-fr",
            7,
            "Décision de recevabilité sous dix jours ouvrés, refus motivé.",
            document="circular-9-w-2016",
        ),
    ]
    legacy = AnswerService(LocalRetriever(base))
    return AssistantService(
        legacy,
        tmp_path,
        domain=(extra, {"domain_loaded": True}),
        approved_hashes={a.id: sha(a.text.encode()) for a in extra},
    )


@pytest.mark.parametrize(
    "question,facets",
    [
        ("Quel système d’information pour les réclamations ?", ["information_system"]),
        ("Quelle formation du personnel aux réclamations ?", ["training"]),
        ("Quelles informations aux clients sur les réclamations ?", ["information"]),
        (
            "Quel délai de traitement de médiation pour une demande recevable ?",
            ["response_deadline"],
        ),
        ("ما أجل معالجة طلب وساطة مقبول؟", ["response_deadline"]),
        ("ما أجل البت في قبول طلب الوساطة؟", ["admissibility"]),
        ("Combien de mois dure le mandat du médiateur ?", ["mandate", "amount"]),
    ],
)
def test_identifies_requested_stage_without_substring_collisions(question, facets):
    assert set(parse(question).facets) == set(facets)


def test_complete_keeps_exception_and_actual_source_language(assistant):
    result = assistant.ask("ما أجل الرد على الشكاية؟", mode="bm25")
    assert result["assessment"]["status"] == "complete"
    assert result["source_language"] == "fr" and result["query_language"] == "ar"
    assert "الظروف" in result["answer"] or "ظروف" in result["answer"]
    assert result["citations"][0]["article_id"] == "4"
    assert result["assessment"]["independent_legal_review"] is False


def test_partial_does_not_invent_compensation(assistant):
    r = assistant.ask(
        "Quel délai de réponse de réclamation et quel montant d’indemnisation ?", mode="bm25"
    )
    assert r["assessment"]["status"] == "partial"
    assert len(r["assessment"]["missing_points"]) >= 1
    assert [c["article_id"] for c in r["citations"]] == ["4"]
    assert "euros" not in r["answer"] and "dirhams" not in r["answer"]


def test_no_claim_when_numeric_parameter_is_not_in_corpus(assistant):
    r = assistant.ask("Quel montant d’indemnisation pour une réclamation ?", mode="bm25")
    assert r["assessment"]["status"] == "absent" and r["citations"] == []


@pytest.mark.parametrize(
    "question,kwargs,status",
    [
        ("Quel délai pour une réclamation ?", {}, "ambiguous"),
        ("Quel délai de réclamation est actuellement applicable ?", {}, "temporal"),
        ("Quel délai de réponse à une réclamation ?", {"as_of": "2019-01-01"}, "temporal"),
        (
            "Quel délai de réponse à une réclamation ?",
            {"institution_type": "payment_institution"},
            "absent",
        ),
    ],
)
def test_clarifies_scope_instead_of_applying_similarity(assistant, question, kwargs, status):
    r = assistant.ask(question, mode="bm25", **kwargs)
    assert r["assessment"]["status"] == status and r["citations"] == []


def test_explicit_arabic_filter_never_invents_circular_translation(assistant):
    r = assistant.ask("ما أجل الرد على الشكاية؟", source_language="ar", mode="bm25")
    assert r["assessment"]["status"] == "absent"
    assert r["citations"] == [] and r["assessment"]["available_source_hint"]


def test_auto_can_use_multiple_documentary_languages(assistant):
    r = assistant.ask("ما الالتزام بآلية الشكايات وما أجل الرد؟", mode="bm25")
    assert r["assessment"]["status"] == "complete"
    assert set(r["source_languages"]) == {"fr", "ar"}
    assert len(r["citations"]) == 2


def test_format_request_stays_missing_even_if_reporting_is_found(assistant):
    r = assistant.ask(
        "Quelle périodicité de reporting des réclamations et quel format JSON ?", mode="bm25"
    )
    assert r["assessment"]["status"] == "partial"
    assert r["assessment"]["claims"][0]["id"] == "complaint-reporting"


def test_catalogue_reference_does_not_override_explicit_article(assistant):
    r = assistant.ask(
        "Quel délai de réponse selon article 3 de la circulaire 10/W/2016 pour les réclamations ?",
        mode="bm25",
    )
    assert r["assessment"]["status"] != "complete"
    assert r["citations"] == []


def test_free_generator_remains_disabled_before_semantic_validation(assistant):
    with pytest.raises(ValueError, match="validation"):
        assistant.ask("Quel délai de réponse à une réclamation ?", mode="bm25", generator="ollama")


def test_unreviewed_extraction_is_rejected(tmp_path):
    base = [article("test-law-fr", 157, "Dispositif interne adapté.", document="law-103-12")]
    extra = [article("bam-complaints-2023-fr", 4, "Transcription différente non approuvée.")]
    with pytest.raises(ValueError, match="Transcription"):
        AssistantService(
            AnswerService(LocalRetriever(base)),
            tmp_path,
            domain=(extra, {"domain_loaded": True}),
            approved_hashes={extra[0].id: "b" * 64},
        )


def test_missing_domain_is_not_reported_loaded(tmp_path):
    assert load_domain(tmp_path) == ([], {"domain_loaded": False})


def test_extraction_removes_layout_but_preserves_legal_footnote_reference():
    text = "header\nPUBLIC\nArticle 3\nMotif juridique.\n433 Arrêté d’homologation\nfooter"
    assert _body(text) == "Article 3\nMotif juridique."
    with pytest.raises(ValueError):
        _body("Unexpected layout")


def test_development_report_never_claims_independent_fidelity(assistant, tmp_path):
    cases = tmp_path / "cases.json"
    cases.write_text(
        json.dumps(
            {
                "status": "development",
                "cases": [
                    {
                        "id": "synthetic",
                        "questions": {
                            "fr": "Quel délai de réponse à une réclamation ?",
                            "ar": "ما أجل الرد على الشكاية؟",
                        },
                        "expected_status": "complete",
                        "expected_facts": ["complaint-response"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    # Resources are real metadata, no external corpus is required for this test.
    r = evaluate_development(assistant, cases, tmp_path / "report", mode="bm25")
    assert r["metrics"]["claim_faithfulness"] == "not_independently_evaluated"
    assert r["metrics"]["status_matches"] == 2
    with pytest.raises(ValueError, match="nouveau dossier"):
        evaluate_development(assistant, cases, tmp_path / "report")


def test_v3_api_rejects_bad_dates_and_generator_without_touching_original(assistant, tmp_path):
    app = create_ui_app(
        Settings(data_dir=tmp_path), answer_service=assistant.legacy, static_dir=tmp_path
    )
    app.state.assistant_service = assistant
    with TestClient(app) as client:
        assert client.get("/assistant/config").json()["profile"]["current_law_verified"] is False
        r = client.post(
            "/assistant/ask",
            json={"question": "Quel délai de réponse à une réclamation ?", "mode": "bm25"},
        )
        assert r.status_code == 200 and r.json()["assessment"]["status"] == "complete"
        assert (
            client.post(
                "/assistant/ask", json={"question": "article 157", "as_of": "yesterday"}
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/assistant/ask", json={"question": "article 157", "generator": "ollama"}
            ).status_code
            == 422
        )
        assert client.post("/ask", json={"question": "article 157"}).status_code == 200
        assert client.get("/assistant/schema").status_code == 200
        assert "/assistant/ask" not in client.get("/openapi.json").json()["paths"]


def test_explicit_circular_lookup_uses_its_own_numbering(assistant):
    result = assistant.ask("Texte article 4 de la circulaire 10/W/2016", mode="bm25")
    assert result["assessment"]["status"] == "complete"
    assert result["citations"][0]["document_id"] == "circular-10-w-2016"


def test_unknown_institution_requires_clarification(assistant):
    result = assistant.ask(
        "Quel délai de réponse à une réclamation ?", mode="bm25", institution_type="unknown"
    )
    assert result["assessment"]["status"] == "ambiguous"
    assert result["assessment"]["clarification"]


def test_foreign_jurisdiction_is_not_assumed_to_be_moroccan(assistant):
    result = assistant.ask("Quel délai de réponse à une réclamation en Espagne ?", mode="bm25")
    assert result["assessment"]["status"] == "absent"
    assert result["citations"] == []


def test_requested_hour_conversion_is_not_claimed_established(assistant):
    result = assistant.ask("Quel délai de réponse à une réclamation en heures ?", mode="bm25")
    assert result["assessment"]["status"] == "partial"
    assert "Calcul calendaire" in result["assessment"]["missing_points"]
