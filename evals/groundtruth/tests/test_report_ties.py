"""Tests for the recall@10 tie in the report's failing-queries heading (Codex review, fix round 1,
Minor 2). report.py:render_report used max() to pick a single "best config", so a tie on recall@10
was hidden. The heading must name every config tied for the highest full-set recall@10."""
from evals.groundtruth import report as report_mod
from evals.groundtruth import run_retrieval
from evals.groundtruth.retriever import RetrievedChunk
from evals.groundtruth.tests.test_run_retrieval import CORPUS, FakeEmbedder, make_config, make_fake_build_retriever, make_item


def _run(monkeypatch, name: str, hit: bool):
    golden = [make_item("A", no_leakage=True, max_shared_ngram=3)]
    hits = {"question A": [RetrievedChunk("doc1", 0, 10, "hit")] if hit
            else [RetrievedChunk("doc1", 90, 100, "miss")]}
    monkeypatch.setattr(run_retrieval, "build_retriever", make_fake_build_retriever(hits))
    result = run_retrieval.run_config(make_config(name), golden, CORPUS, embedder=FakeEmbedder())
    return result, golden


def test_heading_names_every_config_tied_on_recall_at_10(monkeypatch, tmp_path):
    result_a, golden = _run(monkeypatch, "configA", hit=True)
    result_b, _ = _run(monkeypatch, "configB", hit=True)
    golden_path = tmp_path / "golden_set.jsonl"
    golden_path.write_text("".join(g.model_dump_json() + "\n" for g in golden), encoding="utf-8")
    monkeypatch.setattr(report_mod, "GOLDEN_SET", golden_path)

    text = report_mod.render_report([result_a, result_b])

    assert "queries with recall@10 = 0 under best recall@10 config (configA, tied with configB): 0" in text


def test_heading_has_no_tied_with_when_one_config_is_clear_best(monkeypatch, tmp_path):
    result_a, golden = _run(monkeypatch, "configA", hit=False)
    result_b, _ = _run(monkeypatch, "configB", hit=True)
    golden_path = tmp_path / "golden_set.jsonl"
    golden_path.write_text("".join(g.model_dump_json() + "\n" for g in golden), encoding="utf-8")
    monkeypatch.setattr(report_mod, "GOLDEN_SET", golden_path)

    text = report_mod.render_report([result_a, result_b])

    assert "queries with recall@10 = 0 under best recall@10 config (configB): 0" in text
    assert "tied with" not in text
