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
# A single golden question moving from hit to miss shifts MRR by up to 1/59 (~0.017). MAX_MRR_DROP
# is wider than MAX_DROP so the gate catches real regressions, not the noise of one question's rank
# changing by chance.
MAX_MRR_DROP = 0.02
REBUILD = ("Run locally with OPENAI_API_KEY: python -m evals.groundtruth.indexer --config production && "
           "python -m evals.groundtruth.run_retrieval --config production --write-baseline, then commit "
           "evals/groundtruth/indexes, cache/queries and baseline.json")


class BaselineMissingMRR(Exception):
    """baseline.json predates the mrr key."""


def require_mrr(baseline: dict) -> float:
    """Return baseline['mrr'], raising BaselineMissingMRR with the rebuild hint instead of KeyError
    when an older baseline.json has no mrr key."""
    try:
        return baseline["mrr"]
    except KeyError:
        raise BaselineMissingMRR(f"baseline.json has no 'mrr' key. {REBUILD}") from None


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


@pytest.mark.gate
def test_production_mrr_does_not_regress():
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    golden = load_golden(GOLDEN_SET)
    assert baseline["n_golden"] == len(golden), f"golden set changed since baseline. {REBUILD}"
    try:
        baseline_mrr = require_mrr(baseline)
    except BaselineMissingMRR as exc:
        pytest.fail(str(exc))
    embedder = openai_embedder(PRODUCTION.embedder_id, PRODUCTION.embedder_dimensions, CACHE_DIR / "queries", online=False)
    try:
        result = run_config(PRODUCTION, golden, load_corpus(), embedder)
    except EmbeddingCacheMiss as exc:
        pytest.fail(f"query embedding cache is stale: {exc}. {REBUILD}")
    except IndexMismatch as exc:
        pytest.fail(f"committed index is stale: {exc}. {REBUILD}")
    mrr = result["summary"]["overall"]["mrr"]
    assert mrr >= baseline_mrr - MAX_MRR_DROP, (
        f"mrr dropped from {baseline_mrr:.3f} to {mrr:.3f} (max drop {MAX_MRR_DROP})")


def test_require_mrr_returns_the_value_when_present():
    assert require_mrr({"mrr": 0.5944175410277106}) == 0.5944175410277106


def test_require_mrr_fails_with_rebuild_hint_when_key_is_missing():
    with pytest.raises(BaselineMissingMRR) as excinfo:
        require_mrr({"recall@10": 0.9})
    message = str(excinfo.value)
    assert "no 'mrr' key" in message
    assert "run_retrieval --config production --write-baseline" in message
