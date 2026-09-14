"""Deterministic leakage signals between a candidate question and its golden article.

No model runs here. The signals catch a question that copies the article's wording, which inflates
lexical retrieval, and a question that points at a source the user would not have in hand. The
threshold is fixed before looking at the candidates and is not tuned on them.
"""
import re
import unicodedata

NGRAM_FLAG = 5

STOPWORDS = frozenset("""
a ao aos as ate com como da das de do dos e ela ele em entre essa esse esta este eu foi ha isso ja
la mais mas me mesmo na nas nao no nos o os ou para pela pelas pelo pelos por qual quais quando que
quem se sem ser seu sua sao sobre tambem te tem um uma umas uns voce
""".split())

SOURCE_PATTERNS = (
    re.compile(r"\b(art|arts|artigo|artigos|dispositivo|paragrafo|inciso|alinea|caput)\b"),
    re.compile(r"\b(clt|cdc|cpc|lgpd)\b"),
    re.compile(r"\bcodigo de (processo civil|defesa do consumidor)\b"),
    re.compile(r"\blei geral de protecao de dados\b"),
    re.compile(r"\bconsolidacao das leis do trabalho\b"),
    re.compile(r"\blei (n|no|numero)\b"),
    re.compile(r"\blei ((n|no|numero) )?\d"),
    re.compile(r"\bdecreto (lei )?((n|no|numero) )?\d"),
)
SECTION_SIGN = "§"


def fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", fold(text))


def content_tokens(text: str) -> list[str]:
    return [t for t in tokens(text) if len(t) >= 3 and t not in STOPWORDS]


def max_shared_ngram(question: str, passage: str) -> int:
    """Length, in tokens, of the longest run of consecutive question tokens found verbatim in the passage."""
    q, p = tokens(question), tokens(passage)
    positions: dict[str, list[int]] = {}
    for index, token in enumerate(p):
        positions.setdefault(token, []).append(index)
    best = 0
    for i in range(len(q)):
        for j in positions.get(q[i], ()):
            n = 0
            while i + n < len(q) and j + n < len(p) and q[i + n] == p[j + n]:
                n += 1
            best = max(best, n)
    return best


def cites_source(question: str) -> bool:
    if SECTION_SIGN in question:  # tokens() drops "§", so it is checked on the raw question
        return True
    joined = " ".join(tokens(question))
    return any(pattern.search(joined) for pattern in SOURCE_PATTERNS)


def leakage_signals(question: str, passage: str) -> dict:
    q = content_tokens(question)
    p = set(content_tokens(passage))
    overlap = sum(1 for t in q if t in p) / len(q) if q else 0.0
    return {"content_overlap": round(overlap, 4),
            "max_shared_ngram": max_shared_ngram(question, passage),
            "cites_source": cites_source(question)}
