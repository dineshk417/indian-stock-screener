import re
import string

_STOP_WORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "shall", "can", "need", "must",
    "it", "its", "this", "that", "these", "those", "we", "you", "they",
    "he", "she", "i", "me", "my", "your", "our", "their", "his", "her",
    "not", "no", "nor", "so", "yet", "both", "either", "neither", "each",
    "few", "more", "most", "other", "some", "such", "than", "too", "very",
    "just", "also", "as", "if", "then", "than", "when", "where", "who",
    "which", "what", "how", "all", "any", "both", "about", "above", "after",
    "before", "between", "during", "through", "up", "down", "out", "off",
    "over", "under", "again", "further", "once", "here", "there", "while",
})


def _normalize(token: str) -> str:
    return token.lower().strip(string.punctuation).strip()


def tokenize(text: str) -> set[str]:
    words = [_normalize(w) for w in re.split(r"\s+", text) if w]
    words = [w for w in words if w and w not in _STOP_WORDS and len(w) > 1]
    unigrams = set(words)
    bigrams = {f"{words[i]} {words[i+1]}" for i in range(len(words) - 1)}
    return unigrams | bigrams


def score_keywords(resume_text: str, jd_keywords: list[str]) -> dict:
    if not jd_keywords:
        return {"score": 0.0, "matched": [], "missing": []}
    resume_tokens = tokenize(resume_text)
    matched = [kw for kw in jd_keywords if _normalize(kw) in resume_tokens]
    missing = [kw for kw in jd_keywords if _normalize(kw) not in resume_tokens]
    score = round(len(matched) / len(jd_keywords) * 100, 1)
    return {"score": score, "matched": matched, "missing": missing}


def compute_ats_scores(
    resume_text: str,
    tailored_text: str,
    jd_keywords: list[str],
) -> dict:
    return {
        "before": score_keywords(resume_text, jd_keywords),
        "after": score_keywords(tailored_text, jd_keywords),
    }
