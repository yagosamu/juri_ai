"""Binds the committed results/abstention.md to the numbers the detector actually produces, so a
number in the published report cannot drift from the artifact it was measured on. Fully offline.
"""
import json
import re

import pytest

from evals.groundtruth.config import ABSTENTION_BASELINE, ABSTENTION_REPORT, ANSWERS, GENERATION_DIR, SCORES
from evals.groundtruth.generation.refusal import judge_agreement, refusal_counts, row_verdicts
from evals.groundtruth.generation.run_generation import split_by_kind
from evals.groundtruth.golden.jsonl_io import read_jsonl_rows

PRE_ADOPTION_ANSWERS = GENERATION_DIR / "answers_pre_adoption.jsonl"
PRE_ADOPTION_SCORES = GENERATION_DIR / "scores_pre_adoption.json"


@pytest.fixture(scope="module")
def report() -> str:
    return ABSTENTION_REPORT.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def counts() -> dict:
    return refusal_counts(read_jsonl_rows(ANSWERS))


def test_the_report_states_the_two_counts_the_detector_produces(report, counts):
    assert counts == {"n_golden": 30, "n_out_of_scope": 10, "golden_refusals": 1,
                      "out_of_scope_refusals": 10}
    assert "| out of scope | answers detected as an abstention | 10 | 10 | 10 |" in report
    assert "| in scope | golden answers detected as a refusal | 1 | 30 | 1 |" in report


def test_the_report_counts_match_the_committed_baseline(report, counts):
    baseline = json.loads(ABSTENTION_BASELINE.read_text(encoding="utf-8"))
    for key in ("n_golden", "n_out_of_scope", "golden_refusals", "out_of_scope_refusals"):
        assert baseline[key] == counts[key], key


def test_the_report_states_the_agreement_with_the_judges(report):
    rows = read_jsonl_rows(ANSWERS)
    _, oos = split_by_kind(rows)
    stored = json.loads(SCORES.read_text(encoding="utf-8"))["abstention"]
    agreement = judge_agreement(oos, stored)
    assert (agreement["agree"], agreement["n"]) == (10, 10)
    assert agreement["disagreements"] == []
    assert "agrees with the judge label on 10 of 10 rows" in report
    assert "no disagreement to name" in report


def test_the_report_names_r1_cdc_060_with_its_deepeval_scores(report):
    row = next(g for g in json.loads(SCORES.read_text(encoding="utf-8"))["golden"]
               if g["id"] == "r1-cdc-060")
    assert (row["faithfulness_score"], row["relevancy_score"]) == (1.0, 1.0)
    assert "r1-cdc-060" in report
    assert "faithfulness 1.0 and relevancy 1.0" in report
    assert "raises both published means" in report


def test_the_report_states_the_pre_adoption_counts_the_detector_produces(report):
    pre = refusal_counts(read_jsonl_rows(PRE_ADOPTION_ANSWERS))
    assert pre == {"n_golden": 30, "n_out_of_scope": 10, "golden_refusals": 0,
                   "out_of_scope_refusals": 0}
    assert "| pre-adoption | 0 | 10 | 0 | 30 | 3 |" in report
    assert "| 2026-10-06 | 10 | 10 | 1 | 30 | 0 |" in report


def test_the_report_counts_the_pre_adoption_failed_runs_correctly(report):
    _, oos = split_by_kind(read_jsonl_rows(PRE_ADOPTION_ANSWERS))
    failed = [v["id"] for v in row_verdicts(oos) if v["run_failed"]]
    assert failed == ["oos-01", "oos-07", "oos-08"]
    assert "(oos-01, oos-07, oos-08)" in report


def test_the_report_says_what_the_metric_does_not_see(report):
    for claim in ("can undercount", "partial refusal", "committed artifact rather than live behaviour"):
        assert claim in report, claim


def test_the_report_says_the_stored_aggregate_in_scores_json_is_stale(report):
    """A future reader must not cite scores.json's top-level abstention_counts, which disagrees with
    the per-row labels this run was reported from."""
    stored = json.loads(SCORES.read_text(encoding="utf-8"))
    assert stored["abstention_counts"]["abstained"] == 8
    assert sum(1 for item in stored["abstention"] if item["label"] == "abstained") == 10
    assert "stale and nothing reads it" in report


def test_the_report_has_no_em_or_en_dash(report):
    assert "—" not in report
    assert "–" not in report


def test_every_number_the_report_tabulates_for_the_means_comes_from_the_scores(report):
    from evals.groundtruth.generation.scoring import aggregate_faithfulness_relevancy

    golden = json.loads(SCORES.read_text(encoding="utf-8"))["golden"]
    published = aggregate_faithfulness_relevancy(golden)["overall"]
    without = aggregate_faithfulness_relevancy(
        [g for g in golden if g["id"] != "r1-cdc-060"])["overall"]
    for metric, agg in (("faithfulness", published), ("relevancy", published)):
        assert f"{agg[metric]['mean']!r} over n={agg[metric]['n']}" in report, metric
    for metric in ("faithfulness", "relevancy"):
        assert f"{without[metric]['mean']!r} over n={without[metric]['n']}" in report, metric


def test_the_report_links_the_detector_and_the_reproduce_command(report):
    assert "generation/refusal.py" in report
    assert "python -m evals.groundtruth.generation.refusal" in report


def test_the_report_cites_no_gitignored_path():
    """results/*.json is gitignored, so a reader of the committed report cannot open one."""
    text = ABSTENTION_REPORT.read_text(encoding="utf-8")
    assert not re.search(r"results/[\w.-]+\.json", text)
    assert ".superpowers" not in text
