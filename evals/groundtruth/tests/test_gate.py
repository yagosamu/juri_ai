"""CI regression gate. Runs the production retrieval config fully offline and compares recall@10
with baseline.json. Fails loudly when the committed index or query cache is stale."""
import json

import pytest

from evals.groundtruth.config import BASELINE, CACHE_DIR, GOLDEN_SET, PRODUCTION, load_corpus
from evals.groundtruth.embedder_cache import EmbeddingCacheMiss, openai_embedder
from evals.groundtruth.golden.schema import load_golden
from evals.groundtruth.indexer import index_fingerprint
from evals.groundtruth.retriever import IndexMismatch
from evals.groundtruth.run_retrieval import run_config

MAX_DROP = 0.01
REBUILD = ("Run locally with OPENAI_API_KEY: python -m evals.groundtruth.indexer --config production && "
           "python -m evals.groundtruth.run_retrieval --config production --write-baseline, then commit "
           "evals/groundtruth/indexes, cache/queries and baseline.json")


@pytest.mark.gate
def test_production_index_matches_current_retrieval_config():
    assert index_fingerprint(PRODUCTION) == PRODUCTION.fingerprint(), f"committed index is stale. {REBUILD}"


@pytest.mark.gate
def test_production_recall_at_10_does_not_regress():
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    golden = load_golden(GOLDEN_SET)
    assert baseline["n_golden"] == len(golden), f"golden set changed since baseline. {REBUILD}"
    embedder = openai_embedder(PRODUCTION.embedder_id, PRODUCTION.embedder_dimensions, CACHE_DIR / "queries", online=False)
    try:
        result = run_config(PRODUCTION, golden, load_corpus(), embedder)
    except EmbeddingCacheMiss as exc:
        pytest.fail(f"query embedding cache is stale: {exc}. {REBUILD}")
    except IndexMismatch as exc:
        pytest.fail(f"committed index is stale: {exc}. {REBUILD}")
    recall = result["summary"]["overall"]["recall@10"]
    assert recall >= baseline["recall@10"] - MAX_DROP, (
        f"recall@10 dropped from {baseline['recall@10']:.3f} to {recall:.3f} (max drop {MAX_DROP})")
