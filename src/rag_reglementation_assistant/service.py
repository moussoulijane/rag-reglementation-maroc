"""Bounded documentary assistance with explicit, point-level evidence.

Reviewed propositions guide reference expansion; the embedding score never
certifies answerability. This deliberately does not enable free generation.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from time import perf_counter

from rag_reglementation_maroc.models import Article
from rag_reglementation_maroc.text import detect_language, normalize

from .corpus import RESOURCE_DIR, load_domain, sha, source_catalog
from .intent import label, parse
from .knowledge import FACTS
from .retrieval import DomainRetriever

MESSAGES = {
    "complete": (
        "Les points identifiés sont étayés dans les documents cités.",
        "النقاط المحددة مسندة في الوثائق المشار إليها.",
    ),
    "partial": (
        "Certains points sont étayés ; les autres restent non établis.",
        "بعض النقاط مسندة وتبقى النقاط الأخرى غير مثبتة.",
    ),
    "absent": (
        "L’information précise n’est pas établie par les preuves de ce périmètre.",
        "المعلومة الدقيقة غير مثبتة بأدلة هذا النطاق.",
    ),
    "temporal": (
        "Ces éditions documentaires ne permettent pas de certifier la règle à la date demandée.",
        "لا تتيح هذه النسخ الوثائقية تأكيد القاعدة في التاريخ المطلوب.",
    ),
    "ambiguous": (
        "Précisez la source ou l’étape : réception, recevabilité ou réponse, et réclamation ou médiation.",
        "يرجى تحديد المصدر أو المرحلة: التوصل أو القبول أو الرد، وهل يتعلق الأمر بالشكاية أم الوساطة.",
    ),
}
SCOPE = (
    "Lecture des éditions documentaires citées ; actualité et applicabilité individuelle non établies.",
    "قراءة للنسخ الوثائقية المشار إليها؛ لم يثبت سريانها الحالي أو انطباقها على حالة فردية.",
)


class AssistantService:
    def __init__(self, legacy, data_dir: Path, *, domain=None, approved_hashes=None):
        self.legacy = legacy
        extra, quality = load_domain(data_dir) if domain is None else domain
        self.quality = quality
        base = list(legacy.retriever.articles.values())
        self.articles = {a.id: a for a in base + extra}
        if approved_hashes is None:
            approved_hashes = json.loads(
                (RESOURCE_DIR / "reviewed_hashes.json").read_text(encoding="utf-8")
            )
        self.approved_hashes = approved_hashes
        for a in extra:
            if approved_hashes.get(a.id) != sha(a.text.encode()):
                raise ValueError("Transcription métier différente : nouvelle revue requise.")
        self.retriever = DomainRetriever(legacy.retriever, extra, data_dir / "v3/index")
        self.sources = source_catalog(base + extra)

    def config(self, base: dict) -> dict:
        sources = self.sources
        return {
            **base,
            "schema_version": 3,
            "engine_version": "assistant-0.3.0",
            "corpus_version": "2023-12" if self.quality.get("domain_loaded") else "2022-03-31",
            "corpus_label": "Loi 2022 · circulaires du recueil fin 2023"
            if self.quality.get("domain_loaded")
            else "Loi — édition 2022",
            "article_count": len(self.articles),
            "article_count_by_language": {
                lang: sum(a.language == lang for a in self.articles.values())
                for lang in ["fr", "ar"]
            },
            "sources": sources,
            "policy_status": "reviewed_propositions_internal_v1",
            "profile": {
                "id": "client-relations-v1",
                "topics": ["complaints", "mediation"],
                "domain_loaded": self.quality.get("domain_loaded", False),
                "current_law_verified": False,
                "independent_legal_review": False,
                "answerability_method": "bounded_reviewed_propositions",
                "auto_source_language": "all_available_languages",
                "generation_enabled": False,
            },
            "generators": {
                **base["generators"],
                "default": "extractive",
                "choices": ["extractive"],
            },
            "available_modes": ["bm25", "semantic", "hybrid"]
            if self.retriever.encoder is not None
            else ["bm25"],
        }

    def resolve(self, ref: str, language: str | None, query_language: str) -> Article | None:
        if ref.startswith("law:"):
            number = ref.split(":")[1]
            languages = (
                [language]
                if language
                else [query_language, "fr" if query_language == "ar" else "ar"]
            )
            return next(
                (
                    a
                    for lang in languages
                    for a in self.articles.values()
                    if a.document_id == "law-103-12"
                    and a.article_id == number
                    and a.language == lang
                ),
                None,
            )
        a = self.articles.get(ref)
        return a if a is not None and (language is None or a.language == language) else None

    def citation(self, article: Article) -> dict:
        return {
            "chunk_id": f"{article.id}:evidence-{sha(article.text.encode())[:12]}",
            "article_ref": article.id,
            "source_id": article.source_id,
            "document_id": article.document_id,
            "article_id": article.article_id,
            "language": article.language,
            "source_url": article.source_url,
            "page_start": article.page_start,
            "page_end": article.page_end,
            "page_scope": "article",
            "version_date": article.version_date,
            "date_precision": getattr(article, "date_precision", "day"),
            "sha256": article.sha256,
            "quote": article.text,
            "document_title": next(
                s["title"] for s in self.sources if s["id"] == article.source_id
            ),
            "edition_label": next(
                s["edition_label"] for s in self.sources if s["id"] == article.source_id
            ),
            "char_start": 0,
            "char_end": len(article.text),
        }

    def ask(
        self,
        question: str,
        source_language=None,
        mode="semantic",
        top_k=5,
        generator="extractive",
        as_of=None,
        institution_type="credit_institution",
    ) -> dict:
        started = perf_counter()
        if generator != "extractive":
            raise ValueError(
                "La reformulation libre V3 attend sa validation ; utiliser la note sourcée."
            )
        qlang = detect_language(question)
        index = int(qlang == "ar")
        intent = parse(question, as_of)
        # No similar-but-unsupported passages are returned as proof of an answer.
        hits = self.retriever.search(question, language=source_language, mode=mode, top_k=top_k)
        result = {
            "status": "abstained",
            "answer": "",
            "citations": [],
            "query_language": qlang,
            "source_language": source_language or qlang,
            "retriever": mode,
            "generator": "extractive",
            "engine_version": "assistant-0.3.0",
            "corpus_version": "2023-12" if self.quality.get("domain_loaded") else "2022-03-31",
            "corpus_label": "Loi 2022 · recueil fin 2023",
            "policy_status": "reviewed_propositions_internal_v1",
            "semantic_faithfulness": "internal_reviewed_templates_not_independent_validation",
            "reason": None,
            "assessment": {
                "status": "absent",
                "method": "bounded_reviewed_propositions",
                "identified_topics": intent.topics,
                "findings": [],
                "missing_points": [],
                "clarification": None,
                "scope_note": SCOPE[index],
                "requested_as_of": as_of,
                "institution_type": institution_type,
                "independent_legal_review": False,
                "free_generation_enabled": False,
            },
            "trace": {
                "candidate_article_ids": [h.article.id for h in hits],
                "reference_expansion_article_ids": [],
                "selection": "reviewed_reference_expansion",
                "context_budget_utf8_bytes": 12000,
                "context_utf8_bytes": 0,
                "score_is_probability": False,
            },
        }
        assessment = result["assessment"]

        def finish(status):
            assessment["status"] = status
            assessment["message"] = MESSAGES[status][index]
            result["reason"] = None if status == "complete" else f"assistant_{status}"
            result["status"] = "evidence_found" if result["citations"] else "abstained"
            if not result["answer"]:
                result["answer"] = MESSAGES[status][index]
            result["latency_ms"] = round((perf_counter() - started) * 1000, 3)
            # An emitted note always preserves its documentary limits.
            result["source_languages"] = sorted({c["language"] for c in result["citations"]})
            if len(result["source_languages"]) == 1:
                result["source_language"] = result["source_languages"][0]
            return result

        if intent.current:
            assessment["clarification"] = (
                "Voulez-vous une lecture des éditions documentaires disponibles ?"
                if index == 0
                else "هل ترغب في قراءة النسخ الوثائقية المتاحة؟"
            )
            return finish("temporal")
        if re.search(
            r"\b(?:france|espagne|tunisie|algerie|belgique|europe|royaume.uni|etats.unis)\b|فرنسا|اسبانيا|تونس|الجزاير|بلجيكا|اوروبا",
            normalize(question),
        ):
            assessment["missing_points"] = [label("specific", qlang)]
            return finish("absent")
        if institution_type == "unknown":
            assessment["clarification"] = (
                "Quel type d’établissement est concerné ?"
                if index == 0
                else "ما نوع المؤسسة المعنية؟"
            )
            return finish("ambiguous")
        if institution_type not in ["credit_institution", "bank"] or re.search(
            r"etablissement.*paiement|assureur|banque.*france|مؤسس.*اداء", normalize(question)
        ):
            assessment["missing_points"] = [label("specific", qlang)]
            return finish("absent")
        if intent.ambiguous or (
            intent.articles
            and not intent.lookup
            and not intent.document
            and all(int(a.replace("bis", "")) < 16 for a in intent.articles)
        ):
            assessment["clarification"] = MESSAGES["ambiguous"][index]
            return finish("ambiguous")
        citations, by_article = [], {}
        budget = 12000

        def attach(articles):
            # Do not silently truncate a proof or omit one of a claim's sources.
            new = [a for a in articles if a.id not in by_article]
            used = sum(len(c["quote"].encode()) for c in citations)
            if used + sum(len(a.text.encode()) for a in new) > budget:
                return None
            for a in new:
                by_article[a.id] = len(citations) + 1
                citations.append(self.citation(a))
            return [by_article[a.id] for a in articles]

        if intent.lookup:
            for number in intent.articles:
                candidates = [
                    a
                    for a in self.articles.values()
                    if a.article_id == number
                    and (
                        a.document_id == intent.document
                        if intent.document
                        else a.document_id == "law-103-12"
                    )
                    and (a.language == source_language if source_language else a.language == qlang)
                ]
                if not candidates and source_language is None:
                    candidates = [
                        a
                        for a in self.articles.values()
                        if a.article_id == number
                        and a.document_id == (intent.document or "law-103-12")
                    ]
                refs = attach(candidates[:1]) if candidates else None
                assessment["findings"].append(
                    {
                        "key": f"lookup:{number}",
                        "label": f"Article {number}",
                        "state": "supported" if refs else "missing",
                        "claims": [],
                        "citation_indices": refs or [],
                    }
                )
                if not refs:
                    assessment["missing_points"].append(f"Article {number}")
            result["citations"] = citations
            result["answer"] = (
                "Consultation des articles demandés : voir leur texte intégral dans les preuves."
                if index == 0
                else "للاطلاع على المواد المطلوبة، راجع نصوصها في الأدلة."
            )
            result["trace"]["context_utf8_bytes"] = sum(len(c["quote"].encode()) for c in citations)
            return finish(
                "complete"
                if citations and not assessment["missing_points"]
                else "partial"
                if citations
                else "absent"
            )
        if not intent.topics:
            assessment["missing_points"] = [
                (
                    "Question hors du profil réclamations et médiation."
                    if index == 0
                    else "السؤال خارج نطاق الشكايات والوساطة."
                )
            ]
            return finish("absent")
        selected_facts = []
        for topic in intent.topics:
            for facet in intent.facets:
                compatible = [f for f in FACTS if f.topic == topic and facet in f.facets]
                if facet == "overview":
                    compatible = []
                supported = []
                for fact in compatible:
                    articles = [self.resolve(ref, source_language, qlang) for ref in fact.refs]
                    if any(a is None for a in articles):
                        continue
                    if intent.document and any(a.document_id != intent.document for a in articles):
                        continue
                    if intent.articles and any(
                        a.article_id not in intent.articles for a in articles
                    ):
                        continue
                    refs = attach(articles)
                    if refs is None:
                        continue
                    supported.append(
                        {
                            "id": fact.id,
                            "text": fact.ar if index else fact.fr,
                            "citation_indices": refs,
                        }
                    )
                    if fact.id not in [f["id"] for f in selected_facts]:
                        selected_facts.append(supported[-1])
                key = f"{topic}.{facet}"
                assessment["findings"].append(
                    {
                        "key": key,
                        "label": label(facet, qlang),
                        "state": "supported" if supported else "missing",
                        "claims": supported,
                        "citation_indices": sorted(
                            {i for claim in supported for i in claim["citation_indices"]}
                        ),
                    }
                )
                if not supported:
                    assessment["missing_points"].append(label(facet, qlang))
        result["citations"] = citations
        result["answer"] = "\n".join(
            f"{claim['text']} " + "".join(f"[{i}]" for i in claim["citation_indices"])
            for claim in selected_facts
        )
        assessment["missing_points"] = list(dict.fromkeys(assessment["missing_points"]))
        assessment["claims"] = selected_facts
        result["trace"]["context_utf8_bytes"] = sum(len(c["quote"].encode()) for c in citations)
        result["trace"]["reference_expansion_article_ids"] = [
            c["article_ref"]
            for c in citations
            if c["article_ref"] not in result["trace"]["candidate_article_ids"]
        ]
        if source_language == "ar" and any(
            "2023-fr" in ref for f in FACTS if f.topic in intent.topics for ref in f.refs
        ):
            assessment["available_source_hint"] = (
                "Les circulaires du recueil ne sont chargées qu’en français. Le mode automatique peut les consulter."
                if not index
                else "دوريات المجموع محملة بالفرنسية فقط. يمكن للوضع التلقائي الرجوع إليها."
            )
        return finish(
            "complete"
            if citations and not assessment["missing_points"]
            else "partial"
            if citations
            else "absent"
        )
