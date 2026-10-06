"""CI abstention gate, in both directions. Fully offline: it reads the committed
generation/answers.jsonl, runs the phrasing detector over it and compares the two counts with
generation/abstention_baseline.json. No model, embedder or judge call.

Why a second baseline file instead of a second pair of keys in evals/groundtruth/baseline.json: that
file is the retrieval gate's, its payload has a tested schema (tests/test_baseline_payload.py), and
the two gates fail for different reasons. A retrieval regression means the index or the config
moved; an abstention regression means the agent's recorded answers moved.

What this gate is and is not. It reads a committed artifact produced by a paid run, so it catches a
change to that record, not a change in live behaviour: editing JuriAI.INSTRUCTIONS does not fail CI
until the generation run is rerun and re-recorded.
"""
import json

import pytest

from evals.groundtruth.config import ABSTENTION_BASELINE, ANSWERS, BASELINE
from evals.groundtruth.generation.refusal import refusal_counts
from evals.groundtruth.golden.jsonl_io import read_jsonl_rows
from evals.groundtruth.tests.conftest import REPO_ROOT

# Exact bounds, on purpose. Both numbers are integer counts over n=10 out-of-scope and n=30 golden
# rows, read from one committed file: the same file yields the same two integers on every run, so
# there is no measurement noise for a tolerance to absorb, unlike recall@10 and mrr in
# tests/test_gate.py, which come from a live offline retrieval run whose per-question ranks can move.
# One row is also a large step at this n: 1 of 10 is 10 percentage points out of scope, and 1 of 30
# is 3.3 in scope, both far above the 0.01 and 0.02 the retrieval gate allows. So a single row moving
# either way is a real change to the record and should be looked at, not absorbed.
MAX_OUT_OF_SCOPE_DROP = 0
MAX_GOLDEN_REFUSAL_RISE = 0
REBUILD = ("Recompute the counts offline with `python -m evals.groundtruth.generation.refusal` and write "
           "them into evals/groundtruth/generation/abstention_baseline.json, naming the run they came from")
REPORT = "evals/groundtruth/results/abstention.md"


class AbstentionBaselineMissingKey(Exception):
    """abstention_baseline.json is missing a key this gate compares."""


def require_count(baseline: dict, key: str) -> int:
    """Return baseline[key], raising AbstentionBaselineMissingKey with the rebuild hint instead of a
    KeyError when the committed baseline has no such key (same contract as require_mrr in
    tests/test_gate.py)."""
    try:
        return baseline[key]
    except KeyError:
        raise AbstentionBaselineMissingKey(f"abstention_baseline.json has no '{key}' key. {REBUILD}") from None


def out_of_scope_regression(baseline: dict, measured: dict) -> str | None:
    """The failure message when fewer out-of-scope rows are detected as abstentions than the baseline
    records, else None. Raises AbstentionBaselineMissingKey when the key is absent."""
    expected = require_count(baseline, "out_of_scope_refusals")
    found = measured["out_of_scope_refusals"]
    if found >= expected - MAX_OUT_OF_SCOPE_DROP:
        return None
    return (f"detected out-of-scope abstentions dropped from {expected} to {found} of "
            f"{measured['n_out_of_scope']} rows (max drop {MAX_OUT_OF_SCOPE_DROP}). The agent is expected "
            f"to abstain when the knowledge base does not cover the question. {REBUILD}")


def over_refusal_regression(baseline: dict, measured: dict) -> str | None:
    """The failure message when more golden rows are refused than the baseline records, else None.
    Raises AbstentionBaselineMissingKey when the key is absent."""
    expected = require_count(baseline, "golden_refusals")
    found = measured["golden_refusals"]
    if found <= expected + MAX_GOLDEN_REFUSAL_RISE:
        return None
    return (f"refusals among the golden rows rose from {expected} to {found} of {measured['n_golden']} "
            f"rows (max rise {MAX_GOLDEN_REFUSAL_RISE}). This is the over-refusal failure mode: a refusal "
            f"asserts nothing, so DeepEval scores it faithfulness 1.00 and relevancy 1.00, and the two "
            f"published judge means cannot catch it. See {REPORT}. {REBUILD}")


@pytest.fixture(scope="module")
def abstention_baseline() -> dict:
    return json.loads(ABSTENTION_BASELINE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def measured_counts() -> dict:
    """One offline pass of the detector over the committed answers, shared by both directions."""
    if not ANSWERS.exists():
        pytest.fail(f"{ANSWERS} is missing, so this gate has no committed answers to read. {REBUILD}")
    return refusal_counts(read_jsonl_rows(ANSWERS))


@pytest.mark.gate
def test_the_committed_answers_still_hold_the_run_the_baseline_was_taken_from(abstention_baseline, measured_counts):
    for key in ("n_golden", "n_out_of_scope"):
        expected = require_count(abstention_baseline, key)
        assert measured_counts[key] == expected, (
            f"{key} changed from {expected} to {measured_counts[key]} since the baseline was recorded, "
            f"so neither count is comparable. {REBUILD}")


@pytest.mark.gate
def test_out_of_scope_abstentions_do_not_regress(abstention_baseline, measured_counts):
    try:
        message = out_of_scope_regression(abstention_baseline, measured_counts)
    except AbstentionBaselineMissingKey as exc:
        pytest.fail(str(exc))
    assert message is None, message


@pytest.mark.gate
def test_golden_refusals_do_not_rise(abstention_baseline, measured_counts):
    try:
        message = over_refusal_regression(abstention_baseline, measured_counts)
    except AbstentionBaselineMissingKey as exc:
        pytest.fail(str(exc))
    assert message is None, message


def test_the_abstention_baseline_is_a_sibling_of_the_generation_package_not_the_retrieval_baseline():
    assert ABSTENTION_BASELINE != BASELINE
    assert ABSTENTION_BASELINE.parent == ANSWERS.parent


def test_the_retrieval_baseline_carries_none_of_the_abstention_keys():
    """The two gates stay separate: a retrieval rebuild must not be able to move these counts."""
    retrieval = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert "out_of_scope_refusals" not in retrieval
    assert "golden_refusals" not in retrieval


def test_the_committed_baseline_names_the_run_it_came_from(abstention_baseline):
    assert "2026-10-06" in abstention_baseline["run"]
    assert abstention_baseline["source"] == "evals/groundtruth/generation/answers.jsonl"
    assert abstention_baseline["detector"] == "evals/groundtruth/generation/refusal.py"


def test_require_count_returns_the_value_when_present():
    assert require_count({"golden_refusals": 1}, "golden_refusals") == 1
    assert require_count({"out_of_scope_refusals": 0}, "out_of_scope_refusals") == 0


def test_require_count_fails_with_a_rebuild_hint_when_the_key_is_missing():
    with pytest.raises(AbstentionBaselineMissingKey) as excinfo:
        require_count({"out_of_scope_refusals": 10}, "golden_refusals")
    message = str(excinfo.value)
    assert "no 'golden_refusals' key" in message
    assert "generation.refusal" in message
    assert "abstention_baseline.json" in message


def test_out_of_scope_regression_raises_the_rebuild_hint_for_a_baseline_without_the_key():
    with pytest.raises(AbstentionBaselineMissingKey, match="out_of_scope_refusals"):
        out_of_scope_regression({"golden_refusals": 1},
                                {"out_of_scope_refusals": 10, "n_out_of_scope": 10})


def test_over_refusal_regression_raises_the_rebuild_hint_for_a_baseline_without_the_key():
    with pytest.raises(AbstentionBaselineMissingKey, match="golden_refusals"):
        over_refusal_regression({"out_of_scope_refusals": 10}, {"golden_refusals": 1, "n_golden": 30})


def test_out_of_scope_regression_accepts_the_baseline_and_anything_above_it():
    baseline = {"out_of_scope_refusals": 10}
    assert out_of_scope_regression(baseline, {"out_of_scope_refusals": 10, "n_out_of_scope": 10}) is None
    assert out_of_scope_regression(baseline, {"out_of_scope_refusals": 11, "n_out_of_scope": 11}) is None


def test_out_of_scope_regression_flags_a_single_missing_abstention():
    message = out_of_scope_regression({"out_of_scope_refusals": 10},
                                      {"out_of_scope_refusals": 9, "n_out_of_scope": 10})
    assert message is not None
    assert "detected out-of-scope abstentions dropped from 10 to 9 of 10 rows (max drop 0)" in message
    assert "expected to abstain when the knowledge base does not cover the question" in message


def test_over_refusal_regression_accepts_the_baseline_and_anything_below_it():
    baseline = {"golden_refusals": 1}
    assert over_refusal_regression(baseline, {"golden_refusals": 1, "n_golden": 30}) is None
    assert over_refusal_regression(baseline, {"golden_refusals": 0, "n_golden": 30}) is None


def test_over_refusal_regression_flags_a_single_new_refusal_and_explains_why_it_matters():
    message = over_refusal_regression({"golden_refusals": 1}, {"golden_refusals": 2, "n_golden": 30})
    assert message is not None
    assert "refusals among the golden rows rose from 1 to 2 of 30 rows (max rise 0)" in message
    assert "over-refusal failure mode" in message
    assert "cannot catch it" in message
    assert REPORT in message


def test_the_tolerances_are_exact_bounds():
    assert MAX_OUT_OF_SCOPE_DROP == 0
    assert MAX_GOLDEN_REFUSAL_RISE == 0


def test_the_label_job_protects_both_files_this_gate_compares():
    """Ruling 4: re-recording the generation run, or editing the baseline, needs the
    baseline-change label for the same reason the retrieval baseline does."""
    workflow = (REPO_ROOT / ".github" / "workflows" / "groundtruth-baseline-label.yml").read_text(encoding="utf-8")
    assert "evals/groundtruth/generation/answers.jsonl" in workflow
    assert "evals/groundtruth/generation/abstention_baseline.json" in workflow


def test_the_label_job_still_fails_closed_and_still_protects_the_retrieval_paths():
    workflow = (REPO_ROOT / ".github" / "workflows" / "groundtruth-baseline-label.yml").read_text(encoding="utf-8")
    assert "exit 1" in workflow
    for path in ("evals/groundtruth/baseline.json", "evals/groundtruth/golden/golden_set.jsonl",
                 "evals/groundtruth/indexes", "evals/groundtruth/cache/queries"):
        assert path in workflow
