"""Task 18, Ruling 3: LanceDbRetriever over-fetches before agno's cliente_id post-filter and records
the shortfall instead of retrying. See OVERFETCH_FACTOR in evals/groundtruth/retriever.py."""
from types import SimpleNamespace

import pytest
from agno.knowledge.embedder.base import Embedder

from evals.groundtruth import retriever as retriever_mod
from evals.groundtruth.config import BASELINE, CACHE_DIR, GOLDEN_SET, PRODUCTION, RetrievalConfig, load_corpus
from evals.groundtruth.embedder_cache import openai_embedder
from evals.groundtruth.golden.schema import load_golden
from evals.groundtruth.indexer import TENANT, build_index
from evals.groundtruth.retriever import OVERFETCH_FACTOR, LanceDbRetriever
from evals.groundtruth.scorers import Span, score_item


class BagEmbedder(Embedder):
    """Deterministic embedding: counts of 8 keyword buckets, so tests can predict neighbours."""

    words = ["prazo", "recurso", "contrato", "dados", "consumidor", "empregado", "juiz", "multa"]

    def __init__(self):
        self.dimensions = len(self.words)

    def get_embedding(self, text):
        low = text.lower()
        return [float(low.count(w)) + 1e-3 for w in self.words]

    def get_embedding_and_usage(self, text):
        return self.get_embedding(text), None


CORPUS = {
    "a": "Art. 1º O prazo para recurso é de quinze dias. " * 6 + "Art. 2º O juiz decide. " * 6,
    "b": "Art. 1º O consumidor tem direito a dados claros sobre o contrato. " * 8,
}
OTHER_TENANT = TENANT + 1


def _config(**overrides):
    base = dict(name="t", chunk_size=120, chunk_overlap=20, search_type="vector", reranker=None,
                embedder_id="bag", embedder_dimensions=8, max_results=3)
    base.update(overrides)
    return RetrievalConfig(**base)


def _retriever(tmp_path, **overrides):
    cfg = _config(**overrides)
    build_index(cfg, CORPUS, BagEmbedder(), indexes_dir=tmp_path)
    return LanceDbRetriever(cfg, CORPUS, BagEmbedder(), indexes_dir=tmp_path)


class PostFilterDB:
    """Mimics agno's LanceDb.search (lance_db.py:474-503): take the top `limit` rows of a fixed,
    relevance-ordered list, then drop the rows whose meta_data does not match `filters`."""

    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def search(self, query, limit, filters=None):
        self.calls.append({"limit": limit, "filters": filters})
        top = self.rows[:limit]
        return [d for d in top if all(d.meta_data.get(k) == v for k, v in (filters or {}).items())]


def _row(tenant, chunk=1):
    return SimpleNamespace(meta_data={"name": "a", "chunk": chunk, "cliente_id": tenant})


def _one_in_five(n=100):
    """n rows in relevance order where only every fifth belongs to this benchmark's tenant."""
    return [_row(TENANT if i % 5 == 4 else OTHER_TENANT) for i in range(n)]


def test_overfetch_factor_is_ten():
    assert OVERFETCH_FACTOR == 10


def test_overfetching_returns_k_matching_rows_where_the_plain_post_filter_comes_up_short(tmp_path):
    retriever = _retriever(tmp_path)
    retriever.vector_db = PostFilterDB(_one_in_five())

    assert len(retriever.search("q", k=5)) == 5

    retriever.overfetch_factor = 1
    assert len(retriever.search("q", k=5)) == 1


def test_the_limit_passed_to_agno_is_k_times_the_overfetch_factor(tmp_path):
    retriever = _retriever(tmp_path)
    fake = PostFilterDB(_one_in_five())
    retriever.vector_db = fake

    retriever.search("q", k=5)

    assert fake.calls == [{"limit": 5 * OVERFETCH_FACTOR, "filters": {"cliente_id": TENANT}}]
    assert retriever.last_requested_limit == 5 * OVERFETCH_FACTOR


def test_a_shortfall_is_recorded_and_not_retried(tmp_path):
    retriever = _retriever(tmp_path)
    fake = PostFilterDB([_row(OTHER_TENANT)] * 40 + [_row(TENANT)] * 3 + [_row(OTHER_TENANT)] * 40)
    retriever.vector_db = fake

    hits = retriever.search("q", k=5)

    assert len(hits) == 3
    assert len(fake.calls) == 1  # no silent retry with a bigger limit
    assert retriever.last_requested_limit == 50
    assert retriever.last_survivors == 3
    assert retriever.last_shortfall == 2


def test_no_shortfall_when_k_rows_survive(tmp_path):
    retriever = _retriever(tmp_path)
    retriever.vector_db = PostFilterDB(_one_in_five())

    retriever.search("q", k=5)

    assert retriever.last_survivors == 10  # every fifth of the top 50
    assert retriever.last_shortfall == 0


def test_the_reranked_path_keeps_its_candidate_count(tmp_path, monkeypatch):
    # agno reranks every row that survives the filter, so over-fetching there would change which
    # candidates the reranker sees and the rerank numbers in results/report.md.
    monkeypatch.setattr(retriever_mod, "make_reranker", lambda name: None)
    retriever = _retriever(tmp_path, reranker="bge-reranker-v2-m3", rerank_candidates=30)
    fake = PostFilterDB(_one_in_five())
    retriever.vector_db = fake

    hits = retriever.search("q", k=3)

    assert fake.calls[0]["limit"] == 30
    assert len(hits) == 3
    assert retriever.last_requested_limit == 30 and retriever.last_shortfall == 0


def test_the_hybrid_path_is_not_overfetched(tmp_path):
    # hybrid search fuses a vector list and a keyword list, each cut at `limit`, so a longer cut
    # reorders the fused top k; over-fetching it would change the hybrid numbers in results/report.md.
    retriever = _retriever(tmp_path, search_type="hybrid")
    fake = PostFilterDB(_one_in_five())
    retriever.vector_db = fake

    hits = retriever.search("q", k=5)

    assert fake.calls[0]["limit"] == 5
    assert len(hits) == 1
    assert retriever.last_requested_limit == 5 and retriever.last_shortfall == 4


def test_single_tenant_results_do_not_change_with_overfetching(tmp_path):
    retriever = _retriever(tmp_path)
    queries = ["qual o prazo do recurso?", "direitos do consumidor", "o juiz decide", "dados do contrato"]
    for query in queries:
        retriever.overfetch_factor = OVERFETCH_FACTOR
        over = retriever.search(query, k=3)
        retriever.overfetch_factor = 1
        plain = retriever.search(query, k=3)
        assert over == plain


def test_production_index_single_tenant_results_are_unchanged():
    """The committed production index and query cache: every golden question gets the same top 10
    with and without over-fetching, so the numbers in results/report.md stay valid."""
    golden, corpus = load_golden(GOLDEN_SET), load_corpus()
    embedder = openai_embedder(PRODUCTION.embedder_id, PRODUCTION.embedder_dimensions, CACHE_DIR / "queries",
                               online=False)
    retriever = LanceDbRetriever(PRODUCTION, corpus, embedder)
    recalls = []
    for item in golden:
        retriever.overfetch_factor = OVERFETCH_FACTOR
        over = retriever.search(item.question, k=PRODUCTION.max_results)
        assert retriever.last_shortfall == 0
        retriever.overfetch_factor = 1
        plain = retriever.search(item.question, k=PRODUCTION.max_results)
        assert over == plain, item.id
        passages = [Span(p.doc_id, p.start, p.end) for p in item.passages]
        recalls.append(score_item([Span(h.doc_id, h.start, h.end) for h in over], passages)["recall@10"])
    import json

    assert sum(recalls) / len(recalls) == pytest.approx(json.loads(BASELINE.read_text(encoding="utf-8"))["recall@10"])
