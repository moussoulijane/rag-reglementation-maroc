"""Auditable question planning; unknown details never become approved facts."""

import re
from dataclasses import dataclass, field

from rag_reglementation_maroc.text import is_article_lookup, normalize, requested_articles

LABELS = {
    "definition": ("Définition", "التعريف"),
    "response_deadline": ("Délai de réponse et réserves", "أجل الرد والتحفظات"),
    "admissibility": ("Recevabilité", "القبول"),
    "acknowledgement": ("Accusé de réception", "تأكيد التوصل"),
    "extension": ("Prolongation du délai", "تمديد الأجل"),
    "procedure": ("Démarche et conditions", "الخطوات والشروط"),
    "obligation": ("Obligation légale", "الالتزام القانوني"),
    "organization": ("Organisation et responsable", "التنظيم والجهة المسؤولة"),
    "information": ("Information de la clientèle", "إخبار الزبناء"),
    "information_system": ("Système d’information", "نظام المعلومات"),
    "controls": ("Contrôles", "المراقبة"),
    "client_unit": ("Unité relation Clients", "وحدة العلاقة مع الزبناء"),
    "audit": ("Comité d’audit", "لجنة التدقيق"),
    "training": ("Formation", "التكوين"),
    "reporting": ("Reporting", "التقارير"),
    "internal_report": ("Rapport de contrôle interne", "تقرير المراقبة الداخلية"),
    "mandate": ("Mandat du médiateur", "انتداب الوسيط"),
    "confidentiality": ("Confidentialité", "السرية"),
    "outcome": ("Issue de la médiation", "نتيجة الوساطة"),
    "bam_recourse": ("Saisine de Bank Al-Maghrib", "اللجوء إلى بنك المغرب"),
    "amount": ("Montant demandé", "المبلغ المطلوب"),
    "sanction": ("Sanction ou indemnisation", "الجزاء أو التعويض"),
    "format": ("Format ou paramètres exacts", "الشكل أو المعايير الدقيقة"),
    "calendar": ("Calcul calendaire", "الحساب الزمني"),
    "specific": ("Situation particulière demandée", "الحالة الخاصة المطلوبة"),
    "overview": ("Exhaustivité de la synthèse", "شمول الملخص"),
    "unknown": ("Point non identifié avec précision", "نقطة غير محددة بدقة"),
}
PATTERNS = {
    "definition": r"defini|qu.est.ce|constitue|تعريف|ما المقصود|ما معني|ما هي.*شكا|ما هي.*وساط",
    "admissibility": r"recevabil|irrecevab|non.recevab|(?<!\w)(?:ال)?قبول\b|عدم.*قبول",
    "acknowledgement": r"accus[eé]|accuser|اشعار.*توصل|تاكيد.*توصل",
    "extension": r"prolong|prorog|depasse|non.respect|تمديد|تجاوز",
    "procedure": r"comment|demarche|proceder|saisir|saisine|recours|canaux|deposer|كيف|خطوات|مسطر|اللجوء|قنوات|ايداع",
    "obligation": r"oblig|doivent.*dispositif|adhesion|الزام|التزام|ملزم|انخراط|واجب",
    "organization": r"entite centrale|organisa|qui traite|responsable|وحده.*مركزيه|تنظيم|من يعالج|من يتولي|من.*مسوول|من.*مكلف",
    "information": r"informer.*client|information.*client|informations.*client|اخبار.*زب|اطلاع.*زب",
    "information_system": r"systeme d.information|tableaux? de bord|نظام المعلومات|لوحه قياده",
    "controls": r"control|مراقب",
    "client_unit": r"relation.*clients|reunion|semestre|العلاقه.*زب|اجتماع|نصف سن",
    "audit": r"audit|تدقيق",
    "training": r"\bformation\b|\bpersonnel\b|تكوين|العاملين",
    "reporting": r"reporting|periodicite|rapport.*trimestr|تقرير|تقارير|ثلاثه اشهر",
    "internal_report": r"rapport.*control|تقرير.*مراقبه",
    "mandate": r"mandat|انتداب",
    "confidentiality": r"confident|secret|independan|impartial|سريه|سر المهني|حياد|استقلال",
    "outcome": r"accord|echec|transactionnel|proces.verbal|اتفاق|محضر|فشل|صلح",
    "amount": r"montant|plafond|tarif|cout|frais|pourcentage|مبلغ|سقف|تكلف|رسوم|نسبه",
    "sanction": r"sanction|penalit|amende|indemnis|dommages|جزاء|غرام|تعويض|عقوب",
    "format": r"\bformats?\b|\bchamps\b|\bxml\b|\bjson\b|\bapi\b|gabarit|template|حقول|نموذج.*ملف|صيغه",
    "calendar": r"calendair|ferie|date exacte|calcul|vendredi|samedi|dimanche|\bheures?\b|\bminutes?\b|\bouvrables?\b|حساب|تاريخ.*دقيق|العطل|التقويم|ساعات|ساعه|دقايق",
    "specific": r"cyber|fraud|etranger|mineur|succession|swift|cheque|immobilier|assuranc|احتيال|سيبراني|قاصر|اجنبي|شيك|تامين",
}
DEADLINE = r"delai|duree|combien.*(?:temps|jours)|اجل|مده|كم.*يوم"
CURRENT = r"actuel|aujourd|en vigueur|derniere.*version|حاليا|الحالي|الساري|اليوم|(?<!\d)(?:202[4-9]|20[3-9]\d)(?!\d)"


@dataclass
class Intent:
    topics: list[str] = field(default_factory=list)
    facets: list[str] = field(default_factory=list)
    current: bool = False
    ambiguous: bool = False
    lookup: bool = False
    articles: list[str] = field(default_factory=list)
    document: str | None = None


def parse(question: str, as_of: str | None = None) -> Intent:
    q = normalize(question).replace("ة", "ه")
    topics = {
        "complaints": r"reclam|plainte|plaignant|شكا|شكي|تظلم",
        "mediation": r"mediat|وساط|وسيط",
    }
    result = Intent(
        topics=[k for k, p in topics.items() if re.search(p, q)],
        facets=[k for k, p in PATTERNS.items() if re.search(p, q)],
        current=bool(as_of or re.search(CURRENT, q)),
        lookup=is_article_lookup(question),
        articles=requested_articles(question),
    )
    for number, topic in [("10", "complaints"), ("9", "mediation")]:
        if re.search(rf"{number}\s*[/ -]\s*w\s*[/ -]?\s*(?:20)?16", q):
            result.document = f"circular-{number}-w-2016"
            if not result.topics:
                result.topics = [topic]
    if result.articles and result.document and not result.facets:
        result.lookup = True
    if re.search(DEADLINE, q) and not any(
        k in result.facets for k in ["admissibility", "acknowledgement", "mandate"]
    ):
        result.facets.append("response_deadline")
        if "complaints" in result.topics and not re.search(
            r"repond|reponse|trait|معالج|رد|اجاب", q
        ):
            result.ambiguous = True
    if (
        "mandate" in result.facets
        and re.search(r"combien|nombre|duree|mois|annees|كم|عدد|مده", q)
        and not re.search(r"qui fixe|qui definit|من يحدد", q)
    ):
        result.facets.append("amount")
    if re.search(r"bank al.maghrib|\bbam\b|بنك المغرب", q) and re.search(
        r"saisir|recours|اللجوء|رفع", q
    ):
        result.facets.append("bam_recourse")
    if re.search(r"tous|toutes|complet|exhaust|ensemble|جميع|كامل|شامل", q):
        result.facets.append("overview")
    if not result.facets and not result.lookup:
        result.facets = ["unknown"]
        result.ambiguous = bool(result.topics)
    if not result.topics and "response_deadline" in result.facets:
        result.ambiguous = True
    result.facets = list(dict.fromkeys(result.facets))
    return result


def label(key: str, language: str) -> str:
    return LABELS.get(key, (key, key))[language == "ar"]
