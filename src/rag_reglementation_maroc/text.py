"""Normaliser pour chercher sans modifier le texte des citations."""

import re
import unicodedata

_STOPWORDS = set(
    "a au aux avec ce ces cet cette dans de des du elle en et est il ils la le les "
    "leur leurs ou par pas pour que quel quelle quelles quels qui se ses son sur un "
    "une d l qu n s t texte loi selon sont peut peuvent faut comment "
    "في من على إلى الى عن ما هي هو هذا هذه ذلك التي الذي هل و أو او أن ان "
    "التي القانون النص كيف يتم يجب يمكن".split()
)
_TRANSLATION = str.maketrans("أإآىؤئ٠١٢٣٤٥٦٧٨٩", "ااايوي0123456789")
_REFERENCE = re.compile(
    r"(?:\barticles?|المادة|المادتان|المادتين)\s*"
    r"(\d{1,4}\s*(?:bis|المكررة|مكررة)?"
    r"(?:\s*(?:,|،|et|و)\s*\d{1,4}\s*(?:bis|المكررة|مكررة)?)*)"
)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).translate(_TRANSLATION).lower()
    return "".join(
        c
        for c in unicodedata.normalize("NFKD", text.replace("ـ", ""))
        if unicodedata.category(c) != "Mn"
    )


def tokens(text: str) -> list[str]:
    return [
        word
        for word in re.findall(r"[^\W_]+", normalize(text), flags=re.UNICODE)
        if word not in _STOPWORDS and len(word) > 1
    ]


def lexical_overlap(question: str, passage: str) -> float:
    terms = set(tokens(_REFERENCE.sub("", normalize(question))))
    return len(terms & set(tokens(passage))) / len(terms) if terms else 0.0


def detect_language(text: str) -> str:
    letters = [c for c in normalize(text) if unicodedata.category(c).startswith("L")]
    arabic = sum("\u0600" <= c <= "\u06ff" for c in letters)
    return "ar" if arabic and arabic >= len(letters) / 2 else "fr"


def requested_articles(question: str) -> list[str]:
    found = []
    for reference in _REFERENCE.finditer(normalize(question)):
        for match in re.finditer(r"(\d{1,4})\s*(bis|المكررة|مكررة)?", reference[1]):
            item = str(int(match[1])) + ("bis" if match[2] else "")
            if item not in found:
                found.append(item)
    return found


def requested_article(question: str) -> str | None:
    found = requested_articles(question)
    return found[0] if len(found) == 1 else None


def is_article_lookup(question: str) -> bool:
    if not requested_articles(question):
        return False
    remaining = set(tokens(_REFERENCE.sub("", normalize(question))))
    return remaining <= {
        "contenu",
        "dit",
        "disent",
        "textes",
        "montre",
        "affiche",
        "donne",
        "moi",
        "cite",
        "lire",
        "نص",
        "نصوص",
        "اعرض",
        "اذكر",
        "مضمون",
        "المادتين",
    }
