"""Task 18, Rulings 1 and 2: a two-tenant LanceDB index built offline, and the measurement of how
agno's cliente_id post-filter behaves across tenants. See evals/groundtruth/multitenant.py."""
from types import SimpleNamespace

import pytest
from agno.knowledge.embedder.base import Embedder

from evals.groundtruth.config import CACHE_DIR, INDEXES_DIR, PRODUCTION, load_corpus
from evals.groundtruth.embedder_cache import EmbeddingCacheMiss, openai_embedder
from evals.groundtruth.golden.schema import GoldenItem, Passage
from evals.groundtruth.multitenant import (DOC_TENANT, EXPECTED_CHUNKS, TENANT_DOCS, build_multitenant_index,
                                           measure, search_tenant)
from evals.groundtruth.retriever import chunk_offsets
from evals.groundtruth.scorers import Span


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


# Real doc_ids, tiny fake text: build_multitenant_index reads DOC_TENANT by doc_id, so the split
# under test is the real one from the brief (tenant 0: cdc, clt; tenant 1: cpc, lgpd).
TINY_CORPUS = {
    "cdc": "Art. 1º O consumidor tem direito a dados claros sobre o contrato. " * 4,
    "clt": "Art. 1º O empregado tem direito ao prazo de aviso previo. " * 4,
    "cpc": "Art. 1º O juiz decide sobre o recurso no prazo legal. " * 4,
    "lgpd": "Art. 1º Os dados pessoais tem protecao legal no contrato. " * 4,
}


def make_item(id_, doc_id, start, end):
    return GoldenItem(
        id=id_, question=f"question about {doc_id}", category="fato_pontual",
        passages=[Passage(doc_id=doc_id, start=start, end=end)],
        source_article="art1", reviewed_by="tester", reviewed_at="2026-01-01T00:00:00",
        review_mode="judge_consensus",
    )


def test_tenant_docs_split_matches_the_brief():
    assert TENANT_DOCS == {0: ("cdc", "clt"), 1: ("cpc", "lgpd")}
    assert DOC_TENANT == {"cdc": 0, "clt": 0, "cpc": 1, "lgpd": 1}


def test_build_multitenant_index_counts_chunks_per_tenant(tmp_path):
    # Each tiny document is far under the production 5000-character chunk size, so it becomes
    # exactly one chunk: 4 documents, 4 chunks, split 2-2 by TENANT_DOCS.
    counts = build_multitenant_index(TINY_CORPUS, BagEmbedder(), runtime_dir=tmp_path, expected_chunks=4)
    assert counts == {0: 2, 1: 2}


def test_build_multitenant_index_raises_when_the_total_does_not_match(tmp_path):
    with pytest.raises(ValueError) as excinfo:
        build_multitenant_index(TINY_CORPUS, BagEmbedder(), runtime_dir=tmp_path, expected_chunks=999)
    message = str(excinfo.value)
    assert "999" in message and "4" in message


class RecordingFilterDB:
    """Mimics agno's LanceDb.search: returns the top `limit` rows from a fixed relevance-ordered
    list, then drops the ones that do not match `filters`, exactly like lance_db.py:474-503."""

    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def search(self, query, limit, filters=None):
        self.calls.append({"query": query, "limit": limit, "filters": filters})
        top = self.rows[:limit]
        if not filters:
            return top
        return [d for d in top if all(d.meta_data.get(k) == v for k, v in filters.items())]


def test_search_tenant_filters_after_taking_the_top_limit_rows():
    offsets = {"cdc": chunk_offsets(TINY_CORPUS["cdc"], 5000, 0)}
    chunk = next(iter(offsets["cdc"]))
    rows = [
        SimpleNamespace(meta_data={"name": "cdc", "chunk": chunk, "cliente_id": 1}),
        SimpleNamespace(meta_data={"name": "cdc", "chunk": chunk, "cliente_id": 0}),
        SimpleNamespace(meta_data={"name": "cdc", "chunk": chunk, "cliente_id": 1}),
    ]
    vector_db = RecordingFilterDB(rows)

    # tenant 0's only matching row sits at index 1, past a top-1 window.
    assert search_tenant(vector_db, offsets, "q", tenant=0, limit=1) == []
    assert vector_db.calls[-1]["limit"] == 1

    spans = search_tenant(vector_db, offsets, "q", tenant=0, limit=3)
    assert len(spans) == 1
    assert spans[0].doc_id == "cdc"
    start, end = offsets["cdc"][chunk]
    assert spans[0] == Span("cdc", start, end)


def test_measure_reports_rows_recall_and_zero_cross_tenant_leakage(tmp_path):
    build_multitenant_index(TINY_CORPUS, BagEmbedder(), runtime_dir=tmp_path, expected_chunks=4)
    cdc_start, cdc_end = 0, len(TINY_CORPUS["cdc"]) // 2
    cpc_start, cpc_end = 0, len(TINY_CORPUS["cpc"]) // 2
    golden = [make_item("g1", "cdc", cdc_start, cdc_end), make_item("g2", "cpc", cpc_start, cpc_end)]

    rows, cross_tenant_rows = measure(golden, TINY_CORPUS, BagEmbedder(), runtime_dir=tmp_path, overfetch_factor=1)

    assert cross_tenant_rows == 0
    by_id = {r["id"]: r for r in rows}
    assert by_id["g1"]["tenant"] == 0
    assert by_id["g2"]["tenant"] == 1
    assert all(r["rows_after_filter"] >= 1 for r in rows)
    assert all("recall@10" in r and "mrr" in r for r in rows)


def test_measure_overfetch_factor_multiplies_the_requested_limit(tmp_path, monkeypatch):
    build_multitenant_index(TINY_CORPUS, BagEmbedder(), runtime_dir=tmp_path, expected_chunks=4)
    golden = [make_item("g1", "cdc", 0, len(TINY_CORPUS["cdc"]) // 2)]

    calls = []
    import evals.groundtruth.multitenant as multitenant_mod

    real_open = multitenant_mod.open_multitenant_table

    def spying_open(embedder, runtime_dir):
        vector_db = real_open(embedder, runtime_dir)
        original_search = vector_db.search

        def spying_search(query, limit, filters=None):
            calls.append(limit)
            return original_search(query, limit=limit, filters=filters)

        vector_db.search = spying_search
        return vector_db

    monkeypatch.setattr(multitenant_mod, "open_multitenant_table", spying_open)
    multitenant_mod.measure(golden, TINY_CORPUS, BagEmbedder(), runtime_dir=tmp_path, overfetch_factor=7)
    assert calls and all(limit == multitenant_mod.SEARCH_LIMIT * 7 for limit in calls)


# The guard is exercised against stand-in directories patched over the module's INDEXES_DIR and
# CACHE_DIR, so that a missing guard fails this test inside tmp_path instead of dropping the real
# production table (which is what happened on 2026-09-17).
@pytest.mark.parametrize("protected", ["INDEXES_DIR", "CACHE_DIR"])
@pytest.mark.parametrize("subpath", ["", "multitenant/lancedb"])
def test_build_multitenant_index_refuses_protected_directories(tmp_path, monkeypatch, protected, subpath):
    import evals.groundtruth.multitenant as multitenant_mod

    stand_in = tmp_path / "protected"
    stand_in.mkdir()
    monkeypatch.setattr(multitenant_mod, protected, stand_in)
    target = stand_in / subpath if subpath else stand_in
    with pytest.raises(ValueError) as excinfo:
        build_multitenant_index(TINY_CORPUS, BagEmbedder(), runtime_dir=target, expected_chunks=4)
    assert str(stand_in) in str(excinfo.value)
    assert list(stand_in.iterdir()) == []


def test_the_default_runtime_dir_is_not_protected():
    import evals.groundtruth.multitenant as multitenant_mod

    runtime = multitenant_mod.MULTITENANT_RUNTIME_DIR.resolve()
    for protected in (INDEXES_DIR.resolve(), CACHE_DIR.resolve()):
        assert protected not in runtime.parents and runtime != protected


class MissingLgpdEmbedder(BagEmbedder):
    """Raises the cache miss the offline embedder raises, for lgpd's text only."""

    def get_embedding(self, text):
        if "pessoais" in text:
            raise EmbeddingCacheMiss("No cached embedding for text starting 'Art. 1º Os dados pessoais'")
        return super().get_embedding(text)


def test_build_multitenant_index_names_the_document_agno_silently_skipped(tmp_path):
    # agno's Knowledge.insert logs an embedding error and inserts 0 chunks instead of raising, so the
    # per-document count is what turns a cache miss into a loud failure.
    with pytest.raises(ValueError) as excinfo:
        build_multitenant_index(TINY_CORPUS, MissingLgpdEmbedder(), runtime_dir=tmp_path, expected_chunks=4)
    message = str(excinfo.value)
    assert "'lgpd'" in message
    assert "evals.groundtruth.indexer" in message


def test_measure_records_the_non_owning_tenant_and_finds_no_owner_rows_there(tmp_path):
    build_multitenant_index(TINY_CORPUS, BagEmbedder(), runtime_dir=tmp_path, expected_chunks=4)
    golden = [make_item("g1", "cdc", 0, 10), make_item("g2", "lgpd", 0, 10)]

    rows, cross_tenant_rows = measure(golden, TINY_CORPUS, BagEmbedder(), runtime_dir=tmp_path)

    by_id = {r["id"]: r for r in rows}
    assert by_id["g1"]["other_tenant"] == 1 and by_id["g2"]["other_tenant"] == 0
    # the other tenant legitimately returns its own documents, never the owner's
    assert all(r["other_tenant_rows"] == 2 for r in rows)
    assert all(r["owner_rows_in_other_tenant"] == 0 for r in rows)
    assert cross_tenant_rows == 0


def test_measure_counts_a_mistagged_chunk_as_a_cross_tenant_leak(tmp_path, monkeypatch):
    import evals.groundtruth.multitenant as multitenant_mod

    offsets_chunk = next(iter(chunk_offsets(TINY_CORPUS["cdc"], 5000, 0)))
    # a cdc chunk (tenant 0) tagged with tenant 1's cliente_id: a data isolation bug in the index
    leaked = SimpleNamespace(meta_data={"name": "cdc", "chunk": offsets_chunk, "cliente_id": 1})
    monkeypatch.setattr(multitenant_mod, "open_multitenant_table",
                        lambda embedder, runtime_dir: RecordingFilterDB([leaked]))
    golden = [make_item("g1", "cdc", 0, 10)]

    rows, cross_tenant_rows = measure(golden, TINY_CORPUS, BagEmbedder(), runtime_dir=tmp_path)

    assert cross_tenant_rows == 1
    assert rows[0]["rows_after_filter"] == 0
    assert rows[0]["owner_rows_in_other_tenant"] == 1


CHUNK_CACHE = CACHE_DIR / "chunks" / "keys.json"


@pytest.mark.skipif(not CHUNK_CACHE.exists(), reason="cache/chunks is local only (gitignored); absent in CI")
def test_real_corpus_builds_the_production_chunk_count_offline(tmp_path):
    corpus = load_corpus()
    embedder = openai_embedder(PRODUCTION.embedder_id, PRODUCTION.embedder_dimensions, CACHE_DIR / "chunks",
                               online=False)
    counts = build_multitenant_index(corpus, embedder, runtime_dir=tmp_path)
    assert sum(counts.values()) == EXPECTED_CHUNKS == 285
