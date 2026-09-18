"""Unit tests for the payload run_retrieval.py --write-baseline writes to baseline.json. Pure and
offline: no embedder, no retriever, no golden set on disk."""
from evals.groundtruth import run_retrieval
from evals.groundtruth.config import RetrievalConfig


def make_config(name="production"):
    return RetrievalConfig(
        name=name, chunk_size=5000, chunk_overlap=0, search_type="vector", reranker=None,
        embedder_id="text-embedding-3-small", embedder_dimensions=1536,
    )


def make_result(recall_at_10, mrr):
    return {"summary": {"overall": {"recall@1": 0.373, "recall@5": 0.8, "recall@10": recall_at_10,
                                     "mrr": mrr, "ndcg@10": 0.9}}}


def test_build_baseline_includes_mrr_from_summary_overall():
    result = make_result(recall_at_10=0.9152542372881356, mrr=0.5944175410277106)
    payload = run_retrieval.build_baseline(result, make_config(), n_golden=59)
    assert payload["mrr"] == 0.5944175410277106


def test_build_baseline_keeps_existing_keys_unchanged():
    result = make_result(recall_at_10=0.9152542372881356, mrr=0.5944175410277106)
    payload = run_retrieval.build_baseline(result, make_config(), n_golden=59)
    assert payload["config"] == "production"
    assert payload["n_golden"] == 59
    assert payload["recall@10"] == 0.9152542372881356
    assert payload["index_fingerprint"] == make_config().fingerprint()
