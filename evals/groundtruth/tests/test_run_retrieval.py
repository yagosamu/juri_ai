import json

import pytest

from evals.groundtruth import report as report_mod
from evals.groundtruth import run_retrieval
from evals.groundtruth.golden.schema import GoldenItem, LeakageSignals, Passage
from evals.groundtruth.retriever import RetrievedChunk
from evals.groundtruth.scorers import METRICS

CORPUS = {"doc1": "x" * 200}


def make_item(id_, no_leakage=None, max_shared_ngram=None, leakage_present=True):
    leakage = None
    if leakage_present:
        leakage = LeakageSignals(judges={"j1": "none"}, max_shared_ngram=max_shared_ngram, no_leakage=no_leakage)
    return GoldenItem(
        id=id_, question=f"question {id_}", category="fato_pontual",
        passages=[Passage(doc_id="doc1", start=0, end=10)],
        source_article="art1", reviewed_by="tester", reviewed_at="2026-01-01T00:00:00",
        review_mode="judge_consensus", leakage=leakage,
    )


class FakeRetriever:
    name = "fake"

    def __init__(self, hits_by_query):
        self.hits_by_query = hits_by_query

    def search(self, query, k):
        return self.hits_by_query[query]


class FakeEmbedder:
    """Records every text passed to get_embedding, in call order, so a test can assert a query was
    embedded (warmed up) before search() ran."""

    def __init__(self):
        self.calls = []

    def get_embedding(self, text):
        self.calls.append(text)
        return [0.0]


class AssertingRetriever:
    """search() asserts the query is already in the embedder's call record, i.e. that run_config
    warmed up the embedding cache before starting the latency timer, not inside it."""

    name = "asserting"

    def __init__(self, embedder, hits_by_query):
        self.embedder = embedder
        self.hits_by_query = hits_by_query

    def search(self, query, k):
        assert query in self.embedder.calls, (
            f"query {query!r} was not embedded before search() ran; the warm-up call is missing "
            "or happens after the latency timer starts")
        return self.hits_by_query[query]


def make_fake_build_retriever(hits_by_query):
    def fake_build_retriever(config, corpus, embedder):
        return FakeRetriever(hits_by_query)
    return fake_build_retriever


def make_config(name="production"):
    return run_retrieval.RetrievalConfig(
        name=name, chunk_size=1000, chunk_overlap=0, search_type="vector", reranker=None,
        embedder_id="bag", embedder_dimensions=8,
    )


def build_three_item_golden():
    """A: no_leakage true, ngram 3, full hit. B: no_leakage false, ngram 4 (short-copy only), hit
    at rank 3. C: no_leakage false, ngram 6 (neither subset), miss entirely. Different outcomes per
    item so a summary accidentally built from the wrong rows produces different metrics."""
    item_a = make_item("A", no_leakage=True, max_shared_ngram=3)
    item_b = make_item("B", no_leakage=False, max_shared_ngram=4)
    item_c = make_item("C", no_leakage=False, max_shared_ngram=6)
    golden = [item_a, item_b, item_c]
    hits = {
        "question A": [RetrievedChunk("doc1", 0, 10, "hit")],
        "question B": [RetrievedChunk("doc1", 20, 30, "miss"), RetrievedChunk("doc1", 30, 40, "miss"),
                       RetrievedChunk("doc1", 0, 10, "hit")],
        "question C": [RetrievedChunk("doc1", 90, 100, "miss")],
    }
    return golden, hits


def test_item_rows_carry_leakage_and_short_copy_flags(monkeypatch):
    golden, hits = build_three_item_golden()
    monkeypatch.setattr(run_retrieval, "build_retriever", make_fake_build_retriever(hits))
    result = run_retrieval.run_config(make_config(), golden, CORPUS, embedder=FakeEmbedder())
    rows = {row["id"]: row for row in result["items"]}
    assert rows["A"]["no_leakage"] is True
    assert rows["A"]["short_copy"] is True
    assert rows["B"]["no_leakage"] is False
    assert rows["B"]["short_copy"] is True
    assert rows["C"]["no_leakage"] is False
    assert rows["C"]["short_copy"] is False


def test_no_leakage_subset_summary_only_uses_item_a(monkeypatch):
    golden, hits = build_three_item_golden()
    monkeypatch.setattr(run_retrieval, "build_retriever", make_fake_build_retriever(hits))
    result = run_retrieval.run_config(make_config(), golden, CORPUS, embedder=FakeEmbedder())
    no_leak = result["summary_no_leakage"]["overall"]
    assert no_leak["n"] == 1
    assert no_leak["recall@10"] == 1.0
    assert no_leak["mrr"] == 1.0


def test_short_copy_subset_summary_only_uses_items_a_and_b(monkeypatch):
    golden, hits = build_three_item_golden()
    monkeypatch.setattr(run_retrieval, "build_retriever", make_fake_build_retriever(hits))
    result = run_retrieval.run_config(make_config(), golden, CORPUS, embedder=FakeEmbedder())
    short_copy = result["summary_short_copy"]["overall"]
    assert short_copy["n"] == 2
    assert short_copy["recall@10"] == 1.0
    # A hits at rank 1 (mrr 1.0), B hits at rank 3 (mrr 1/3): mean is not 1.0, which would be the
    # value if the subset were built from the wrong rows (e.g. including only A, or all three).
    assert short_copy["mrr"] == (1.0 + 1 / 3) / 2


def test_short_copy_boundary_is_strictly_less_than_ngram_flag(monkeypatch):
    """A golden item with max_shared_ngram exactly NGRAM_FLAG is not short-copy."""
    golden, hits = build_three_item_golden()
    item_boundary = make_item("D", no_leakage=False, max_shared_ngram=run_retrieval.NGRAM_FLAG)
    golden.append(item_boundary)
    hits["question D"] = [RetrievedChunk("doc1", 0, 10, "hit")]
    monkeypatch.setattr(run_retrieval, "build_retriever", make_fake_build_retriever(hits))
    result = run_retrieval.run_config(make_config(), golden, CORPUS, embedder=FakeEmbedder())
    rows = {row["id"]: row for row in result["items"]}
    assert rows["D"]["short_copy"] is False
    assert rows["D"]["no_leakage"] is False


def test_embedding_is_warmed_up_before_the_latency_timer(monkeypatch):
    """run_config must call embedder.get_embedding(item.question) before starting the per-item
    timer, so latency measures retriever.search alone and not an embedding-API cache miss."""
    golden, hits = build_three_item_golden()
    embedder = FakeEmbedder()

    def fake_build_retriever(config, corpus, emb):
        return AssertingRetriever(emb, hits)

    monkeypatch.setattr(run_retrieval, "build_retriever", fake_build_retriever)
    run_retrieval.run_config(make_config(), golden, CORPUS, embedder=embedder)
    assert embedder.calls == ["question A", "question B", "question C"]


def test_item_without_leakage_signals_gets_both_flags_false(monkeypatch):
    golden, hits = build_three_item_golden()
    item_none = make_item("E", leakage_present=False)
    golden.append(item_none)
    hits["question E"] = [RetrievedChunk("doc1", 0, 10, "hit")]
    monkeypatch.setattr(run_retrieval, "build_retriever", make_fake_build_retriever(hits))
    result = run_retrieval.run_config(make_config(), golden, CORPUS, embedder=FakeEmbedder())
    rows = {row["id"]: row for row in result["items"]}
    assert rows["E"]["no_leakage"] is False
    assert rows["E"]["short_copy"] is False


def _fake_results(tmp_path, monkeypatch):
    """Two fake results/*.json-shaped dicts as run_config would produce them, one with an empty
    short-copy subset so the report must render '-' for its metrics."""
    golden, hits = build_three_item_golden()
    monkeypatch.setattr(run_retrieval, "build_retriever", make_fake_build_retriever(hits))
    result = run_retrieval.run_config(make_config("configA"), golden, CORPUS, embedder=FakeEmbedder())

    # A second config where nothing is short-copy, to exercise the empty-subset "-" rendering.
    golden_empty = [make_item("Z", no_leakage=False, max_shared_ngram=99)]
    hits_empty = {"question Z": [RetrievedChunk("doc1", 90, 100, "miss")]}
    monkeypatch.setattr(run_retrieval, "build_retriever", make_fake_build_retriever(hits_empty))
    result_empty = run_retrieval.run_config(make_config("configB"), golden_empty, CORPUS, embedder=FakeEmbedder())

    golden_path = tmp_path / "golden_set.jsonl"
    golden_path.write_text("".join(g.model_dump_json() + "\n" for g in golden + golden_empty), encoding="utf-8")
    return [result, result_empty], golden_path


def test_render_report_includes_both_subset_tables_in_order(monkeypatch, tmp_path):
    results, golden_path = _fake_results(tmp_path, monkeypatch)
    monkeypatch.setattr(report_mod, "GOLDEN_SET", golden_path)
    text = report_mod.render_report(results)

    spec_idx = text.index("no-leakage subset (spec)")
    robustness_idx = text.index("short-copy subset (robustness view)")
    assert spec_idx < robustness_idx
    assert "| configA | 1 |" in text
    assert "| configB | 0 |" in text
    # configB's short-copy subset is empty: every metric column renders as "-", not just one of them.
    lines = text.splitlines()
    robustness_start = next(i for i, line in enumerate(lines) if line.startswith("short-copy subset (robustness view)"))
    robustness_table = "\n".join(lines[robustness_start:])
    configb_line = next(line for line in robustness_table.splitlines() if line.startswith("| configB |"))
    assert configb_line == "| configB | 0 | " + " | ".join("-" for _ in METRICS) + " |"


def test_render_report_raises_on_empty_results():
    with pytest.raises(ValueError) as excinfo:
        report_mod.render_report([])
    message = str(excinfo.value)
    assert "python -m evals.groundtruth.run_retrieval --config production" in message
