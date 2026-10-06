"""Task 23: a reranker that hands its candidates back unreranked leaves no trace in the harness.

That is the cause behind the `r1-cdc-056` difference between the 2026-09-15 `rerank` run and today's:
agno 2.4.7's `Reranker.rerank` catches every exception raised by `_rerank`, logs it and returns the
candidates in their incoming order (`agno/knowledge/reranker/sentence_transformer.py:49-54`). The
incoming order is LanceDB's distance order, so the run recorded plain vector search for that one
question under the `rerank` label, and nothing in `results/rerank.json` says so. See
`results/rerank_silent_fallback.md`.

These tests pin the behaviour, they do not change it. `make_reranker` still returns agno's class.
"""
from typing import List

import pytest
from agno.knowledge.document import Document
from agno.knowledge.reranker.base import Reranker

from evals.groundtruth import retriever as retriever_mod
from evals.groundtruth.config import RetrievalConfig
from evals.groundtruth.indexer import build_index
from evals.groundtruth.retriever import LanceDbRetriever
from evals.groundtruth.tests.test_overfetch import CORPUS, BagEmbedder

# CORPUS chunks into 11 rows at 120/20, so CANDIDATES below that keeps the shortfall at 0 and the
# comparison about the reranker rather than about a short table.
CANDIDATES = 8
K = 5


class SwallowingReranker(Reranker):
    """agno's except branch, isolated: scoring failed, so the candidates come back untouched."""

    def rerank(self, query: str, documents: List[Document]) -> List[Document]:
        return documents


class ReversingReranker(Reranker):
    """A reranker that does reorder, so the comparison above cannot pass by accident."""

    def rerank(self, query: str, documents: List[Document]) -> List[Document]:
        return list(reversed(documents))


def _config():
    return RetrievalConfig(name="t", chunk_size=120, chunk_overlap=20, search_type="vector",
                           reranker="bge-reranker-v2-m3", rerank_candidates=CANDIDATES,
                           embedder_id="bag", embedder_dimensions=8, max_results=K)


def _retriever(tmp_path, monkeypatch, reranker):
    """A retriever over a scratch table whose reranker is `reranker`, built once per tmp_path."""
    cfg = _config()
    if not (tmp_path / f"{cfg.index_name}.lance").exists():
        build_index(cfg, CORPUS, BagEmbedder(), indexes_dir=tmp_path)
    monkeypatch.setattr(retriever_mod, "make_reranker", lambda name: reranker)
    return LanceDbRetriever(cfg, CORPUS, BagEmbedder(), indexes_dir=tmp_path)


QUERIES = ["qual o prazo do recurso?", "direitos do consumidor", "o juiz decide", "dados do contrato"]


def test_a_swallowed_rerank_returns_the_distance_order(tmp_path, monkeypatch):
    """The fallback output is exactly the first k rows LanceDB returned, in LanceDB's order."""
    swallowed = _retriever(tmp_path, monkeypatch, SwallowingReranker())
    unreranked = _retriever(tmp_path, monkeypatch, None)

    for query in QUERIES:
        assert swallowed.search(query, k=K) == unreranked.search(query, k=K), query


def test_the_harness_records_nothing_that_tells_a_swallowed_rerank_from_a_real_one(tmp_path, monkeypatch):
    """Every field LanceDbRetriever keeps about a search is the same either way, so a run that fell
    back for some questions and reranked the rest is indistinguishable from one that reranked all."""
    recorded = []
    for reranker in (SwallowingReranker(), ReversingReranker()):
        retriever = _retriever(tmp_path, monkeypatch, reranker)
        retriever.search(QUERIES[0], k=K)
        recorded.append((retriever.last_requested_limit, retriever.last_survivors, retriever.last_shortfall))

    assert recorded[0] == recorded[1] == (CANDIDATES, CANDIDATES, 0)


def test_a_reranker_that_reorders_does_change_the_output(tmp_path, monkeypatch):
    """Non-vacuity: the equality above is a property of the fallback, not of this fixture."""
    swallowed = _retriever(tmp_path, monkeypatch, SwallowingReranker())
    reversed_ = _retriever(tmp_path, monkeypatch, ReversingReranker())

    assert swallowed.search(QUERIES[0], k=K) != reversed_.search(QUERIES[0], k=K)


def test_agno_returns_the_candidates_unreranked_when_scoring_raises(monkeypatch):
    """The library behaviour itself, pinned. Skipped where sentence-transformers is not installed,
    which includes CI; `_rerank` is patched out, so no model is loaded."""
    pytest.importorskip("sentence_transformers")
    from agno.knowledge.reranker.sentence_transformer import SentenceTransformerReranker

    def raises(self, query, documents):
        raise RuntimeError("scoring failed")

    monkeypatch.setattr(SentenceTransformerReranker, "_rerank", raises)
    documents = [Document(id=str(i), name="a", content=f"chunk {i}", meta_data={"chunk": i}) for i in range(4)]

    out = SentenceTransformerReranker(model="BAAI/bge-reranker-v2-m3").rerank(query="q", documents=documents)

    assert [d.id for d in out] == ["0", "1", "2", "3"]
    assert all(d.reranking_score is None for d in out)
