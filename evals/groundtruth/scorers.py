"""Retrieval metrics over character spans. Binary relevance: a retrieved chunk is relevant to a
golden passage when it covers at least HIT_THRESHOLD of the passage. Each golden passage is credited
once, to the first chunk that hits it, so a passage split across several overlapping chunks does not
count twice; that credit-once rule is per passage, not per chunk, so a single chunk that happens to
cover two different, still-uncredited passages credits both of them, since both were genuinely found."""
import math
from collections import defaultdict
from dataclasses import dataclass

HIT_THRESHOLD = 0.5
KS = (1, 5, 10)
METRICS = ("recall@1", "recall@5", "recall@10", "mrr", "ndcg@10")


@dataclass(frozen=True)
class Span:
    doc_id: str
    start: int
    end: int

    def __post_init__(self) -> None:
        if not (0 <= self.start < self.end):
            raise ValueError(f"Span requires 0 <= start < end, got start={self.start}, end={self.end}")


def overlap_ratio(chunk: Span, passage: Span) -> float:
    if chunk.doc_id != passage.doc_id:
        return 0.0
    inter = min(chunk.end, passage.end) - max(chunk.start, passage.start)
    return max(0, inter) / (passage.end - passage.start)


def is_hit(chunk: Span, passage: Span, threshold: float = HIT_THRESHOLD) -> bool:
    return overlap_ratio(chunk, passage) >= threshold


def _credits_per_rank(retrieved: list[Span], passages: list[Span]) -> list[set[int]]:
    """For each chunk in rank order, the set of passage indices it newly credits: the still-
    uncredited passages it hits. A passage is credited at most once, to the first chunk that hits
    it; a single chunk may appear in the result crediting more than one passage when it hits several
    distinct passages that no earlier chunk had already credited."""
    credited: set[int] = set()
    assignments: list[set[int]] = []
    for chunk in retrieved:
        newly = {i for i, passage in enumerate(passages) if i not in credited and is_hit(chunk, passage)}
        credited |= newly
        assignments.append(newly)
    return assignments


def hits_per_rank(retrieved: list[Span], passages: list[Span]) -> list[bool]:
    """Binary per-rank relevance used by mrr and ndcg_at_k: True at a rank iff that chunk newly
    credited at least one passage, regardless of how many. Relevance here stays binary on purpose;
    it is recall_at_k, not this function, that counts distinct passages found."""
    return [bool(newly) for newly in _credits_per_rank(retrieved, passages)]


def recall_at_k(retrieved: list[Span], passages: list[Span], k: int) -> float:
    """Count of distinct golden passages credited by any chunk within the top k, divided by the
    total number of passages. A chunk that covers two different passages credits both."""
    credited: set[int] = set()
    for newly in _credits_per_rank(retrieved[:k], passages):
        credited |= newly
    return len(credited) / len(passages)


def mrr(retrieved: list[Span], passages: list[Span]) -> float:
    for rank, hit in enumerate(hits_per_rank(retrieved, passages), start=1):
        if hit:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved: list[Span], passages: list[Span], k: int) -> float:
    gains = hits_per_rank(retrieved[:k], passages)
    dcg = sum(1.0 / math.log2(i + 2) for i, g in enumerate(gains) if g)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(min(len(passages), k)))
    return dcg / idcg if idcg else 0.0


def score_item(retrieved: list[Span], passages: list[Span]) -> dict[str, float]:
    scores = {f"recall@{k}": recall_at_k(retrieved, passages, k) for k in KS}
    scores["mrr"] = mrr(retrieved, passages)
    scores["ndcg@10"] = ndcg_at_k(retrieved, passages, 10)
    return scores


def aggregate(rows: list[dict]) -> dict:
    """rows: dicts with 'category' plus any subset of METRICS. Returns means overall and per
    category. The metric key set is the union across the whole group (not just its first row), and
    each metric is averaged only over the rows that actually carry it, so the result does not depend
    on row order or on every row carrying every metric. 'n' is always the total row count."""
    def mean_of(group: list[dict]) -> dict:
        keys = [m for m in METRICS if any(m in r for r in group)]
        out = {}
        for m in keys:
            vals = [r[m] for r in group if m in r]
            out[m] = sum(vals) / len(vals)
        out["n"] = len(group)
        return out

    by_cat: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_cat[r["category"]].append(r)
    return {"overall": mean_of(rows), "by_category": {c: mean_of(g) for c, g in sorted(by_cat.items())}}
