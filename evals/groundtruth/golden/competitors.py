"""Find articles, other than the golden one, that might also answer a candidate question.

Two methods on purpose: BM25 over folded content tokens and cosine similarity over
text-embedding-3-large article vectors. Neither is what the benchmark measures, which is
text-embedding-3-small over 5000-character chunks, so the evidence handed to the judge does not
favour one configuration under test. A competitor both methods miss remains possible and is a
documented limitation.
"""
import math
from collections import Counter
from dataclasses import dataclass

import numpy as np

from evals.groundtruth.golden.articles import split_articles
from evals.groundtruth.golden.leakage import content_tokens

COMPETITOR_MODEL = "text-embedding-3-large"
COMPETITOR_DIMENSIONS = 3072
EMBED_MAX_CHARS = 8000  # measured 2026-09-14: only clt Art. 922, 24,314 chars, exceeds this
TOP_K = 5


@dataclass(frozen=True)
class ArticleRef:
    ref_id: str
    doc_id: str
    header: str
    start: int
    end: int


def article_refs(corpus: dict[str, str]) -> list[ArticleRef]:
    refs = []
    for doc_id in sorted(corpus):
        for a in split_articles(corpus[doc_id]):
            refs.append(ArticleRef(f"{doc_id}:{a.start}", doc_id, a.header, a.start, a.end))
    return refs


class BM25:
    def __init__(self, documents: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.counts = [Counter(d) for d in documents]
        self.lengths = [len(d) for d in documents]
        self.avg = sum(self.lengths) / len(self.lengths) if documents else 0.0
        n = len(documents)
        df = Counter(t for d in documents for t in set(d))
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
        self.k1, self.b = k1, b

    def scores(self, query: list[str]) -> list[float]:
        out = []
        for counts, length in zip(self.counts, self.lengths):
            score = 0.0
            for term in set(query):
                f = counts.get(term, 0)
                if f:
                    norm = self.k1 * (1 - self.b + self.b * length / self.avg)
                    score += self.idf[term] * f * (self.k1 + 1) / (f + norm)
            out.append(score)
        return out


def embed_articles(refs: list[ArticleRef], corpus: dict[str, str], embedder, save_every: int = 100) -> np.ndarray:
    rows = []
    for n, r in enumerate(refs, start=1):
        rows.append(embedder.get_embedding(corpus[r.doc_id][r.start:r.end][:EMBED_MAX_CHARS]))
        if n % save_every == 0:
            embedder.save()
    embedder.save()
    matrix = np.asarray(rows, dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    if (norms == 0).any():
        raise ValueError("an article embedding has zero norm")
    return matrix / norms


def _top(scores, k: int, exclude: int) -> list[int]:
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    return [i for i in order if i != exclude and scores[i] > 0][:k]


def find_competitors(question: str, golden_index: int, refs: list[ArticleRef], bm25: BM25,
                     question_vector: np.ndarray, article_matrix: np.ndarray, k: int = TOP_K) -> list[dict]:
    merged: dict[int, list[str]] = {}
    for i in _top(bm25.scores(content_tokens(question)), k, golden_index):
        merged.setdefault(i, []).append("bm25")
    for i in _top(list(article_matrix @ question_vector), k, golden_index):
        merged.setdefault(i, []).append("dense")
    return [{"ref_id": refs[i].ref_id, "doc_id": refs[i].doc_id, "header": refs[i].header,
             "start": refs[i].start, "end": refs[i].end, "methods": methods}
            for i, methods in merged.items()]
