"""Tests for evals/groundtruth/significance.py (Task 15, brief 2026-09-13/task-15-brief.md).
Every hand-built example below has a known answer computed independently of the implementation,
so a broken formula fails loudly instead of silently matching whatever the code happens to produce."""
import math

import numpy as np
import pytest

from evals.groundtruth import significance as significance_mod
from evals.groundtruth.config import GOLDEN_SET, RESULTS_DIR
from evals.groundtruth.golden.schema import load_golden
from evals.groundtruth.significance import (assert_golden_size, assert_no_leakage_size,
                                             assert_result_coverage, bootstrap_interval,
                                             build_significance_report, holm, mcnemar_exact,
                                             paired_mean_difference, per_item, render_significance,
                                             sign_flip_p)


# ---------------------------------------------------------------------------
# per_item
# ---------------------------------------------------------------------------

def test_per_item_extracts_the_three_pre_registered_metrics_by_id():
    result = {"config": {"name": "chunk1500"}, "items": [
        {"id": "a", "category": "conceito", "recall@1": 1.0, "recall@5": 1.0, "recall@10": 1.0,
         "mrr": 1.0, "ndcg@10": 1.0},
        {"id": "b", "category": "fato_pontual", "recall@1": 0.0, "recall@5": 1.0, "recall@10": 1.0,
         "mrr": 0.5, "ndcg@10": 0.7},
    ]}

    out = per_item(result)

    assert out == {
        "a": {"recall@1": 1.0, "recall@10": 1.0, "mrr": 1.0},
        "b": {"recall@1": 0.0, "recall@10": 1.0, "mrr": 0.5},
    }


# ---------------------------------------------------------------------------
# bootstrap_interval
# ---------------------------------------------------------------------------

def test_bootstrap_interval_mean_is_the_exact_sample_mean():
    values = [0.0, 1.0, 1.0, 1.0]
    rng = np.random.default_rng(1)

    mean, low, high = bootstrap_interval(values, rng, 1000)

    assert mean == 0.75
    assert 0.0 <= low <= mean <= high <= 1.0


def test_bootstrap_interval_is_deterministic_with_a_fresh_seed():
    values = [0.2, 0.4, 0.6, 0.8, 1.0]

    result_a = bootstrap_interval(values, np.random.default_rng(20260917), 500)
    result_b = bootstrap_interval(values, np.random.default_rng(20260917), 500)

    assert result_a == result_b


def test_bootstrap_interval_on_constant_values_has_zero_width():
    values = [0.5, 0.5, 0.5, 0.5]
    rng = np.random.default_rng(3)

    mean, low, high = bootstrap_interval(values, rng, 200)

    assert (mean, low, high) == (0.5, 0.5, 0.5)


# ---------------------------------------------------------------------------
# mcnemar_exact
# ---------------------------------------------------------------------------

def test_mcnemar_exact_counts_b_and_c():
    # first hits only on items 0 and 2; second hits only on item 1.
    first = [1, 0, 1, 0]
    second = [0, 1, 0, 0]

    result = mcnemar_exact(first, second)

    assert result["b"] == 2  # first=1, second=0
    assert result["c"] == 1  # first=0, second=1


def test_mcnemar_exact_p_is_one_when_no_discordant_pairs():
    result = mcnemar_exact([1, 0, 1], [1, 0, 1])

    assert result == {"b": 0, "c": 0, "p": 1.0}


def test_mcnemar_exact_p_matches_hand_computed_binomial_tail():
    # b=0, c=5: n=5, k=min(b,c)=0. P(X<=0) with X~Binomial(5, 0.5) is (1/2)**5 = 1/32.
    # p = min(1, 2 * 1/32) = 1/16 = 0.0625.
    result = mcnemar_exact([0, 0, 0, 0, 0], [1, 1, 1, 1, 1])

    assert result["b"] == 0
    assert result["c"] == 5
    assert result["p"] == pytest.approx(0.0625)


def test_mcnemar_exact_is_symmetric_in_b_and_c():
    a = mcnemar_exact([0, 0, 0, 0, 0], [1, 1, 1, 1, 1])
    b = mcnemar_exact([1, 1, 1, 1, 1], [0, 0, 0, 0, 0])

    assert a["p"] == b["p"]
    assert a["b"] == b["c"]
    assert a["c"] == b["b"]


def test_mcnemar_exact_p_matches_hand_computed_value_for_b1_c1():
    # b=1, c=1: n=2, k=1. P(X<=1) with X~Binomial(2, 0.5) = (C(2,0)+C(2,1)) * 0.25 = 0.75.
    # p = min(1, 1.5) = 1.0.
    result = mcnemar_exact([1, 0], [0, 1])

    assert result == {"b": 1, "c": 1, "p": 1.0}


def test_mcnemar_exact_rejects_mismatched_lengths():
    with pytest.raises(ValueError):
        mcnemar_exact([1, 0], [1, 0, 1])


# ---------------------------------------------------------------------------
# paired_mean_difference
# ---------------------------------------------------------------------------

def test_paired_mean_difference_matches_hand_computed_mean():
    first = [1.0, 0.5, 0.0, 1.0]
    second = [0.0, 0.5, 0.0, 0.0]
    rng = np.random.default_rng(5)

    result = paired_mean_difference(first, second, rng, 500)

    assert result["difference"] == pytest.approx(0.5)
    assert result["low"] <= result["difference"] <= result["high"]


def test_paired_mean_difference_on_constant_diff_has_zero_width_interval():
    first = [1.0, 1.0, 1.0]
    second = [0.0, 0.0, 0.0]
    rng = np.random.default_rng(7)

    result = paired_mean_difference(first, second, rng, 300)

    assert result == {"difference": 1.0, "low": 1.0, "high": 1.0}


def test_paired_mean_difference_is_deterministic_with_a_fresh_seed():
    first = [0.3, 0.6, 0.9, 0.1]
    second = [0.1, 0.4, 0.2, 0.2]

    a = paired_mean_difference(first, second, np.random.default_rng(20260917), 400)
    b = paired_mean_difference(first, second, np.random.default_rng(20260917), 400)

    assert a == b


# ---------------------------------------------------------------------------
# sign_flip_p
# ---------------------------------------------------------------------------

def test_sign_flip_p_is_one_when_the_two_configs_are_identical():
    first = [0.5, 0.2, 0.9, 0.0]
    second = [0.5, 0.2, 0.9, 0.0]
    rng = np.random.default_rng(11)

    p = sign_flip_p(first, second, rng, 200)

    assert p == 1.0


def test_sign_flip_p_is_deterministic_with_a_fresh_seed():
    first = [1.0, 0.5, 0.0, 1.0, 0.3]
    second = [0.0, 0.5, 0.0, 0.0, 0.9]

    a = sign_flip_p(first, second, np.random.default_rng(20260917), 500)
    b = sign_flip_p(first, second, np.random.default_rng(20260917), 500)

    assert a == b


def test_sign_flip_p_is_between_zero_and_one():
    first = [1.0, 0.5, 0.0, 1.0, 0.3, 0.2]
    second = [0.0, 0.5, 0.0, 0.0, 0.9, 0.8]
    rng = np.random.default_rng(13)

    p = sign_flip_p(first, second, rng, 1000)

    assert 0.0 < p <= 1.0


# ---------------------------------------------------------------------------
# holm
# ---------------------------------------------------------------------------

def test_holm_matches_hand_computed_textbook_example():
    # p = [0.01, 0.02, 0.03, 0.04], m=4, already sorted ascending.
    # rank0: 4*0.01=0.04 -> running max 0.04
    # rank1: 3*0.02=0.06 -> running max 0.06
    # rank2: 2*0.03=0.06 -> running max 0.06
    # rank3: 1*0.04=0.04 -> running max 0.06
    # adjusted = [0.04, 0.06, 0.06, 0.06]
    adjusted = holm([0.01, 0.02, 0.03, 0.04])

    assert adjusted == pytest.approx([0.04, 0.06, 0.06, 0.06])


def test_holm_matches_hand_computed_example_out_of_order():
    # Same four raw p-values as above, permuted: index0=0.04, index1=0.01, index2=0.03, index3=0.02.
    # Sorted ascending by value: idx1(0.01), idx3(0.02), idx2(0.03), idx0(0.04).
    # rank0: 4*0.01=0.04 -> adjusted[1]=0.04, running max 0.04
    # rank1: 3*0.02=0.06 -> adjusted[3]=0.06, running max 0.06
    # rank2: 2*0.03=0.06 -> adjusted[2]=0.06, running max 0.06
    # rank3: 1*0.04=0.04 -> adjusted[0]=max(0.06,0.04)=0.06
    adjusted = holm([0.04, 0.01, 0.03, 0.02])

    assert adjusted == pytest.approx([0.06, 0.04, 0.06, 0.06])


def test_holm_caps_adjusted_p_values_at_one():
    adjusted = holm([0.5, 0.9, 0.99])

    assert all(p <= 1.0 for p in adjusted)


def test_holm_preserves_length_and_order():
    raw = [0.2, 0.001, 0.05, 0.5, 0.03]

    adjusted = holm(raw)

    assert len(adjusted) == len(raw)
    # the smallest raw p-value must not have the smallest adjusted p-value by coincidence only;
    # check monotonic non-decreasing adjusted values when sorted by raw p.
    order = sorted(range(len(raw)), key=lambda i: raw[i])
    adjusted_in_raw_order = [adjusted[i] for i in order]
    assert adjusted_in_raw_order == sorted(adjusted_in_raw_order)


# ---------------------------------------------------------------------------
# render_significance
# ---------------------------------------------------------------------------

def _tiny_intervals():
    return {
        "full (n=2)": {
            "production": {"recall@1": (0.5, 0.0, 1.0), "recall@10": (0.5, 0.0, 1.0), "mrr": (0.5, 0.0, 1.0)},
            "chunk1500": {"recall@1": (1.0, 1.0, 1.0), "recall@10": (1.0, 1.0, 1.0), "mrr": (1.0, 1.0, 1.0)},
        },
    }


def _tiny_comparisons():
    return {
        "full (n=2)": {
            "recall@1": [{"pair": ("chunk1500", "production"), "b": 1, "c": 0, "p": 0.5, "p_holm": 0.5}],
            "recall@10": [{"pair": ("chunk1500", "production"), "b": 1, "c": 0, "p": 0.5, "p_holm": 0.5}],
            "mrr": [{"pair": ("chunk1500", "production"), "difference": 0.5, "low": -0.1, "high": 1.0,
                     "p": 0.5, "p_holm": 0.5}],
        },
    }


def test_render_significance_states_seed_counts_and_alpha():
    text = render_significance(_tiny_intervals(), _tiny_comparisons(),
                                seed=20260917, n_resamples=10000, n_permutations=10000, alpha=0.05)

    assert "20260917" in text
    assert "10000" in text
    assert "0.05" in text


def test_render_significance_states_pairs_were_fixed_before_running():
    text = render_significance(_tiny_intervals(), _tiny_comparisons(),
                                seed=20260917, n_resamples=10000, n_permutations=10000, alpha=0.05)

    assert "before" in text.lower()


def test_render_significance_has_an_intervals_table_per_view():
    text = render_significance(_tiny_intervals(), _tiny_comparisons(),
                                seed=20260917, n_resamples=10000, n_permutations=10000, alpha=0.05)

    assert "full (n=2)" in text
    assert "production" in text
    assert "chunk1500" in text


def test_render_significance_reports_raw_and_holm_p_for_each_pair():
    text = render_significance(_tiny_intervals(), _tiny_comparisons(),
                                seed=20260917, n_resamples=10000, n_permutations=10000, alpha=0.05)

    assert "chunk1500" in text and "production" in text
    assert text.count("0.5") >= 2  # raw p and holm p both appear for the mrr row


def test_render_significance_explains_an_interval_crossing_zero():
    text = render_significance(_tiny_intervals(), _tiny_comparisons(),
                                seed=20260917, n_resamples=10000, n_permutations=10000, alpha=0.05)

    assert "zero" in text.lower()


def test_render_significance_has_no_em_dash_or_en_dash():
    text = render_significance(_tiny_intervals(), _tiny_comparisons(),
                                seed=20260917, n_resamples=10000, n_permutations=10000, alpha=0.05)

    assert "—" not in text
    assert "–" not in text


def test_render_significance_does_not_cite_the_gitignored_brief_path():
    # Fix round 1, Important 2: .superpowers/ is gitignored, so a reader of the committed report
    # cannot open that path. The report must point only at committed artifacts (this module and
    # its commit history), never at the brief file.
    text = render_significance(_tiny_intervals(), _tiny_comparisons(),
                                seed=20260917, n_resamples=10000, n_permutations=10000, alpha=0.05)

    assert ".superpowers" not in text
    assert "task-15-brief" not in text


# ---------------------------------------------------------------------------
# Fix round 1, Important 1: registered sample sizes are enforced, not just dynamically labeled.
# ---------------------------------------------------------------------------

def test_assert_golden_size_accepts_exactly_59_unique_ids():
    assert_golden_size([f"id-{i}" for i in range(59)]) is None  # does not raise


def test_assert_golden_size_rejects_a_different_count():
    with pytest.raises(ValueError, match="58"):
        assert_golden_size([f"id-{i}" for i in range(58)])


def test_assert_golden_size_rejects_duplicates_even_at_the_right_count():
    ids = [f"id-{i}" for i in range(58)] + ["id-0"]  # 59 entries, but id-0 repeats
    with pytest.raises(ValueError, match="duplicate"):
        assert_golden_size(ids)


def test_assert_result_coverage_accepts_an_exact_match():
    assert_result_coverage("chunk1500.json", ["a", "b", "c"], ["c", "b", "a"]) is None


def test_assert_result_coverage_rejects_a_missing_id():
    with pytest.raises(ValueError, match=r"missing.*\['c'\]"):
        assert_result_coverage("chunk1500.json", ["a", "b"], ["a", "b", "c"])


def test_assert_result_coverage_rejects_an_extra_id():
    with pytest.raises(ValueError, match=r"extra.*\['d'\]"):
        assert_result_coverage("chunk1500.json", ["a", "b", "c", "d"], ["a", "b", "c"])


def test_assert_result_coverage_rejects_a_duplicate_id():
    with pytest.raises(ValueError, match="duplicate"):
        assert_result_coverage("chunk1500.json", ["a", "a", "b"], ["a", "b"])


def test_assert_no_leakage_size_accepts_exactly_20_unique_ids():
    assert_no_leakage_size([f"id-{i}" for i in range(20)]) is None


def test_assert_no_leakage_size_rejects_a_different_count():
    with pytest.raises(ValueError, match="19"):
        assert_no_leakage_size([f"id-{i}" for i in range(19)])


def test_assert_no_leakage_size_rejects_duplicates():
    ids = [f"id-{i}" for i in range(19)] + ["id-0"]  # 20 entries, id-0 repeats
    with pytest.raises(ValueError, match="duplicate"):
        assert_no_leakage_size(ids)


# ---------------------------------------------------------------------------
# Fix round 1, Important 3: the exact binomial tail must not overflow for large discordant counts.
# ---------------------------------------------------------------------------

def test_mcnemar_exact_handles_large_balanced_counts_without_overflow():
    # b=c=1000: a direct comb(n, k) * 0.5 ** n evaluation raises OverflowError, because
    # comb(2000, 1000) alone exceeds the largest representable float before the 0.5 ** 2000 factor
    # gets a chance to shrink it back down. The tail must be computed in exact integer arithmetic.
    first = [1] * 1000 + [0] * 1000
    second = [0] * 1000 + [1] * 1000

    result = mcnemar_exact(first, second)

    assert result["b"] == 1000
    assert result["c"] == 1000
    assert result["p"] == 1.0


def test_mcnemar_exact_matches_hand_computed_value_for_unequal_nonzero_b_and_c():
    # b=3, c=1: n=4, k=min(3,1)=1. P(X<=1) with X~Binomial(4, 0.5) = (C(4,0)+C(4,1))/16 = 5/16.
    # p = min(1, 2 * 5/16) = min(1, 10/16) = 0.625. A wrong b+c (e.g. treating n as just b, or c)
    # would not reproduce this value.
    first = [1, 1, 1, 0]
    second = [0, 0, 0, 1]

    result = mcnemar_exact(first, second)

    assert result["b"] == 3
    assert result["c"] == 1
    assert result["p"] == pytest.approx(0.625)


# ---------------------------------------------------------------------------
# Fix round 1, Important 4: paired resampling must share one index between first and second, and
# sign_flip_p's +1 correction must be exercised by an exact expected value.
# ---------------------------------------------------------------------------

def test_paired_mean_difference_shares_one_index_not_independent_resampling():
    # Anti-correlated data: second = 5 - first, so every per-item difference is odd
    # ({-3, -1, 1, 3}). Under PAIRED resampling (one shared random index per resample draws the
    # same item from both arrays), every resampled mean is an average of a multiset drawn from
    # that fixed set of 4 odd values. An INDEPENDENT implementation (separate index arrays for
    # first and second) could pair first[i] with second[j] for i != j, producing differences like
    # 0 or 2 that a paired resample can never produce, and would consume twice as many random
    # draws from the shared rng, desynchronizing every later call. The reference below is a
    # deliberately non-vectorized (loop-based) reimplementation, not the module's own formula,
    # using the identical rng seed: numpy.random.default_rng(seed).integers(0, n, size=(R, n))
    # and R separate default_rng(seed).integers(0, n, size=n) calls draw the identical sequence.
    first = [1.0, 2.0, 3.0, 4.0]
    second = [4.0, 3.0, 2.0, 1.0]
    n = 4
    n_resamples = 500

    actual = paired_mean_difference(first, second, np.random.default_rng(99), n_resamples)

    ref_rng = np.random.default_rng(99)
    diffs = [f - s for f, s in zip(first, second)]
    resampled_means = []
    for _ in range(n_resamples):
        picks = ref_rng.integers(0, n, size=n)
        resampled_means.append(sum(diffs[i] for i in picks) / n)
    expected_low, expected_high = np.percentile(resampled_means, [2.5, 97.5])

    assert actual["difference"] == pytest.approx(0.0)
    assert actual["low"] == pytest.approx(float(expected_low))
    assert actual["high"] == pytest.approx(float(expected_high))
    # every value the paired reference can produce is a multiple of 0.5 (sum of 4 odd numbers is
    # even, divided by 4); this is the property an independent implementation would not respect.
    assert all(abs(m * 2 - round(m * 2)) < 1e-9 for m in resampled_means)


def test_sign_flip_p_matches_hand_computed_value_with_plus_one_correction():
    # first=[3,1,0], second=[0,0,0]: diffs=[3,1,0], observed |mean| = 4/3.
    # With numpy.random.default_rng(1), the 4 sign draws for n=3 are
    # [[-1,1,1],[1,-1,-1],[1,1,-1],[-1,1,-1]], giving permuted means [2/3, 2/3, 4/3, 2/3]; only the
    # third permutation reaches the observed value, so count=1.
    # p = (1 + count) / (1 + n_permutations) = 2/5 = 0.4. Without the +1 correction (count /
    # n_permutations), this would instead be 1/4 = 0.25, so removing it changes the result.
    first = [3.0, 1.0, 0.0]
    second = [0.0, 0.0, 0.0]

    p = sign_flip_p(first, second, np.random.default_rng(1), 4)

    assert p == pytest.approx(0.4)


# ---------------------------------------------------------------------------
# Fix round 1, Minor 1: empty samples raise instead of silently producing NaN.
# ---------------------------------------------------------------------------

def test_bootstrap_interval_rejects_an_empty_sequence():
    with pytest.raises(ValueError):
        bootstrap_interval([], np.random.default_rng(1), 100)


def test_paired_mean_difference_rejects_empty_sequences():
    with pytest.raises(ValueError):
        paired_mean_difference([], [], np.random.default_rng(1), 100)


# ---------------------------------------------------------------------------
# Fix round 1, Important 5: an end-to-end test binds the registered constants and the real inputs
# to the committed results/significance.md. results/*.json is gitignored, so this test must skip
# cleanly (never fail) when those files are absent, e.g. on a fresh CI checkout.
# ---------------------------------------------------------------------------

def test_build_significance_report_matches_the_committed_report_byte_for_byte():
    missing = [name for name in significance_mod.CONFIG_ORDER
               if not (RESULTS_DIR / f"{name}.json").exists()]
    if missing or not GOLDEN_SET.exists():
        pytest.skip(f"results/*.json not present (gitignored): missing {missing}")

    results = significance_mod._load_results()
    golden = load_golden(GOLDEN_SET)

    # the registered constants themselves, pinned so a silent edit to any of them is caught here
    # even though the byte-for-byte comparison below would also catch it.
    assert significance_mod.SEED == 20260917
    assert significance_mod.N_RESAMPLES == 10_000
    assert significance_mod.N_PERMUTATIONS == 10_000
    assert significance_mod.ALPHA == 0.05
    assert significance_mod.METRICS == ("recall@1", "recall@10", "mrr")
    assert significance_mod.PAIRS == (
        ("chunk1500", "production"), ("chunk800", "chunk1500"), ("hybrid", "chunk1500"),
        ("rerank", "chunk1500"), ("hybrid", "rerank"))

    golden_ids = sorted(g.id for g in golden)
    assert len(golden_ids) == significance_mod.N_GOLDEN
    no_leakage_ids = sorted(g.id for g in golden if g.leakage and g.leakage.no_leakage)
    assert len(no_leakage_ids) == significance_mod.N_NO_LEAKAGE

    actual = build_significance_report(results, golden)
    committed = (RESULTS_DIR / "significance.md").read_text(encoding="utf-8")

    assert actual == committed
