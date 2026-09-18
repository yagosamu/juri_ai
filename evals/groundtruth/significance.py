"""Pre-registered bootstrap intervals and paired significance tests for the retrieval comparison.
The pairs, metrics, views, seed, resample and permutation counts and alpha below are this module's
own constants, fixed before it first ran and unchanged since; its commit history is the public
record of that.

The unit is one golden question. Every golden item has exactly one passage, so recall@1 and
recall@10 are 0 or 1 per item; build_significance_report() asserts this, and asserts the registered
sample sizes (59 unique golden ids, 20 no-leakage ids, every result covering exactly the golden
ids), before computing anything. Metrics: recall@1, recall@10 and MRR. Views: the full set (n=59)
and the no-leakage subset (n=20, `leakage.no_leakage` true in `golden/golden_set.jsonl`). Bootstrap:
95% percentile intervals from 10,000 resamples of items with replacement, seeded with
`numpy.random.default_rng(20260917)`. Pairs, in this fixed order: chunk1500 vs production, chunk800
vs chunk1500, hybrid vs chunk1500, rerank vs chunk1500, hybrid vs rerank. Binary metrics use the
two-sided exact McNemar test on discordant pairs. MRR uses a paired bootstrap interval of the mean
difference plus a two-sided sign-flip permutation p-value. Multiplicity: Holm-adjusted p-values
across the five pairs, separately per metric and view. Standard library and numpy only; no other
dependency.

Usage: .venv/Scripts/python.exe -m evals.groundtruth.significance
"""
import json
import math
import sys
from fractions import Fraction

import numpy as np

from evals.groundtruth.config import GOLDEN_SET, RESULTS_DIR
from evals.groundtruth.golden.schema import load_golden

SEED = 20260917
N_RESAMPLES = 10_000
N_PERMUTATIONS = 10_000
ALPHA = 0.05
N_GOLDEN = 59
N_NO_LEAKAGE = 20
METRICS = ("recall@1", "recall@10", "mrr")
BINARY_METRICS = ("recall@1", "recall@10")
CONFIG_ORDER = ("production", "chunk1500", "chunk800", "hybrid", "rerank")
PAIRS = (
    ("chunk1500", "production"),
    ("chunk800", "chunk1500"),
    ("hybrid", "chunk1500"),
    ("rerank", "chunk1500"),
    ("hybrid", "rerank"),
)


def per_item(result: dict) -> dict[str, dict[str, float]]:
    """id -> {metric: value} for the pre-registered metrics only (recall@1, recall@10, mrr)."""
    return {item["id"]: {m: item[m] for m in METRICS} for item in result["items"]}


def _find_duplicates(ids: list[str]) -> list[str]:
    seen: set[str] = set()
    dupes: set[str] = set()
    for i in ids:
        if i in seen:
            dupes.add(i)
        seen.add(i)
    return sorted(dupes)


def assert_golden_size(golden_ids: list[str], expected: int = N_GOLDEN) -> None:
    """Raises ValueError unless golden_ids has no duplicates and exactly `expected` ids. Guards the
    pre-registered unit count (n=59 golden questions) against a changed or corrupted golden set."""
    dupes = _find_duplicates(golden_ids)
    if dupes:
        raise ValueError(f"golden set has duplicate ids: {dupes}")
    if len(golden_ids) != expected:
        raise ValueError(f"golden set has {len(golden_ids)} ids, expected exactly {expected}")


def assert_result_coverage(name: str, result_ids: list[str], golden_ids: list[str]) -> None:
    """Raises ValueError unless result_ids has no duplicates and covers exactly golden_ids (no
    missing id, no extra id)."""
    dupes = _find_duplicates(result_ids)
    if dupes:
        raise ValueError(f"{name} has duplicate ids: {dupes}")
    missing = sorted(set(golden_ids) - set(result_ids))
    extra = sorted(set(result_ids) - set(golden_ids))
    if missing or extra:
        raise ValueError(
            f"{name} does not cover exactly the {len(golden_ids)} golden ids "
            f"(missing {missing}, extra {extra})")


def assert_no_leakage_size(no_leakage_ids: list[str], expected: int = N_NO_LEAKAGE) -> None:
    """Raises ValueError unless no_leakage_ids has no duplicates and exactly `expected` ids. Guards
    the pre-registered no-leakage subset count (n=20) against a changed leakage labeling."""
    dupes = _find_duplicates(no_leakage_ids)
    if dupes:
        raise ValueError(f"no-leakage subset has duplicate ids: {dupes}")
    if len(no_leakage_ids) != expected:
        raise ValueError(f"no-leakage subset has {len(no_leakage_ids)} ids, expected exactly {expected}")


def bootstrap_interval(values, rng, n_resamples) -> tuple[float, float, float]:
    """Percentile bootstrap of the mean: resample n items with replacement n_resamples times and
    take the 2.5th and 97.5th percentiles of the resampled means. Returns (mean, low, high). Raises
    ValueError on an empty sequence instead of returning a NaN mean."""
    values = np.asarray(values, dtype=float)
    n = len(values)
    if n == 0:
        raise ValueError("bootstrap_interval requires at least one value, got an empty sequence")
    mean = float(values.mean())
    idx = rng.integers(0, n, size=(n_resamples, n))
    resampled_means = values[idx].mean(axis=1)
    low, high = np.percentile(resampled_means, [2.5, 97.5])
    return mean, float(low), float(high)


def _binom_tail_le(k: int, n: int) -> float:
    """P(X <= k) for X ~ Binomial(n, 0.5), computed in exact integer arithmetic (a sum of
    math.comb terms over an exact Fraction denominator 2**n) and converted to float once at the
    end. A direct `comb(n, k) * 0.5 ** n` overflows for large n (e.g. n=2000): comb(n, k) alone can
    exceed the largest representable float, so `float(comb(n, k))` raises OverflowError before the
    0.5 ** n factor ever gets a chance to shrink it back down. Fraction keeps numerator and
    denominator as exact integers throughout and only converts at the very end, where Python's
    big-int true division computes the correctly rounded float directly without ever materializing
    an intermediate value too large to represent."""
    total = sum(math.comb(n, i) for i in range(k + 1))
    return float(Fraction(total, 1 << n))


def mcnemar_exact(first: list[int], second: list[int]) -> dict:
    """Two-sided exact McNemar test on paired binary outcomes. b: items where only first hits.
    c: items where only second hits. p = min(1, 2 * P(X <= min(b, c))) with X ~ Binomial(b + c, 0.5),
    and p = 1 when b + c = 0."""
    if len(first) != len(second):
        raise ValueError(f"first and second must be paired, same length, got {len(first)} and {len(second)}")
    b = sum(1 for f, s in zip(first, second) if f == 1 and s == 0)
    c = sum(1 for f, s in zip(first, second) if f == 0 and s == 1)
    n = b + c
    if n == 0:
        p = 1.0
    else:
        k = min(b, c)
        p = min(1.0, 2 * _binom_tail_le(k, n))
    return {"b": b, "c": c, "p": p}


def paired_mean_difference(first, second, rng, n_resamples) -> dict:
    """Bootstrap 95% interval of the mean paired difference (first minus second): resample the
    paired differences with replacement n_resamples times, one shared random index per resample
    applied to both arrays so the pairing survives resampling. Returns {difference, low, high}.
    Raises ValueError on an empty sequence instead of returning a NaN difference."""
    first = np.asarray(first, dtype=float)
    second = np.asarray(second, dtype=float)
    diffs = first - second
    n = len(diffs)
    if n == 0:
        raise ValueError("paired_mean_difference requires at least one paired value, got an empty sequence")
    difference = float(diffs.mean())
    idx = rng.integers(0, n, size=(n_resamples, n))
    resampled_means = diffs[idx].mean(axis=1)
    low, high = np.percentile(resampled_means, [2.5, 97.5])
    return {"difference": difference, "low": float(low), "high": float(high)}


def sign_flip_p(first, second, rng, n_permutations) -> float:
    """Two-sided sign-flip permutation p-value on the paired differences (first minus second):
    p = (1 + count(|permuted mean| >= |observed mean|)) / (1 + n_permutations)."""
    first = np.asarray(first, dtype=float)
    second = np.asarray(second, dtype=float)
    diffs = first - second
    n = len(diffs)
    if n == 0:
        return 1.0
    observed = abs(float(diffs.mean()))
    signs = rng.integers(0, 2, size=(n_permutations, n)) * 2 - 1
    permuted_means = np.abs((diffs[None, :] * signs).mean(axis=1))
    count = int(np.sum(permuted_means >= observed))
    return (1 + count) / (1 + n_permutations)


def holm(p_values: list[float]) -> list[float]:
    """Holm step-down multiplicity correction. Returns adjusted p-values in the same order as the
    input, each capped at 1.0 and monotone non-decreasing when read in ascending order of the raw
    p-value."""
    m = len(p_values)
    order = sorted(range(m), key=lambda i: p_values[i])
    adjusted = [0.0] * m
    running_max = 0.0
    for rank, i in enumerate(order):
        candidate = (m - rank) * p_values[i]
        running_max = max(running_max, candidate)
        adjusted[i] = min(1.0, running_max)
    return adjusted


def _fmt(x: float, digits: int = 3) -> str:
    return f"{x:.{digits}f}"


def render_significance(intervals: dict, comparisons: dict, *, seed: int, n_resamples: int,
                         n_permutations: int, alpha: float) -> str:
    """intervals: view -> config -> metric -> (mean, low, high).
    comparisons: view -> metric -> list of rows in the fixed pair order, each a dict with keys
    'pair' (first, second) plus either {'b', 'c', 'p', 'p_holm'} for a binary metric or
    {'difference', 'low', 'high', 'p', 'p_holm'} for mrr."""
    lines = [
        "# Retrieval significance",
        "",
        "Pre-registered analysis for the retrieval comparison. The five pairs (in the order below), "
        "the metrics, the views, the seed, the resample and permutation counts and the multiplicity "
        "correction are this module's own constants; they were fixed before it first ran and were "
        "not changed after seeing any result. The commit history of "
        "`evals/groundtruth/significance.py` is the public record of when they were set.",
        "",
        f"Seed: {seed}. Bootstrap resamples: {n_resamples}. Sign-flip permutations: {n_permutations}. "
        f"Alpha: {alpha}.",
        "",
    ]

    for view, by_config in intervals.items():
        lines.append(f"## Intervals, {view}")
        lines.append("")
        lines.append("| config | " + " | ".join(f"{m} (95% CI)" for m in METRICS) + " |")
        lines.append("|" + "---|" * (len(METRICS) + 1))
        for config in CONFIG_ORDER:
            if config not in by_config:
                continue
            cells = []
            for m in METRICS:
                mean, low, high = by_config[config][m]
                cells.append(f"{_fmt(mean)} [{_fmt(low)}, {_fmt(high)}]")
            lines.append(f"| {config} | " + " | ".join(cells) + " |")
        lines.append("")

    for view, by_metric in comparisons.items():
        lines.append(f"## Comparisons, {view}")
        lines.append("")
        lines.append("| pair | metric | first | second | b, c or difference interval | raw p | Holm p |")
        lines.append("|---|---|---|---|---|---|---|")
        config_intervals = intervals[view]
        for metric in METRICS:
            for row in by_metric[metric]:
                first_name, second_name = row["pair"]
                first_mean = _fmt(config_intervals[first_name][metric][0])
                second_mean = _fmt(config_intervals[second_name][metric][0])
                if metric in BINARY_METRICS:
                    evidence = f"b={row['b']}, c={row['c']}"
                else:
                    evidence = f"diff={_fmt(row['difference'])} [{_fmt(row['low'])}, {_fmt(row['high'])}]"
                lines.append(
                    f"| {first_name} vs {second_name} | {metric} | {first_mean} | {second_mean} | "
                    f"{evidence} | {_fmt(row['p'], 4)} | {_fmt(row['p_holm'], 4)} |")
        lines.append("")

    lines.append(
        "How to read a difference interval that crosses zero: when the 95% interval for a mean "
        "difference includes zero, the data do not rule out no difference between the two configs "
        "at that confidence level, even if the point estimate favors one side. A raw or Holm-adjusted "
        "p-value above alpha carries the same reading for the paired tests above.")
    lines.append("")
    return "\n".join(lines)


def _load_results() -> dict[str, dict]:
    results = {}
    for name in CONFIG_ORDER:
        path = RESULTS_DIR / f"{name}.json"
        results[name] = json.loads(path.read_text(encoding="utf-8"))
    return results


def build_significance_report(results: dict[str, dict], golden: list) -> str:
    """Pure: turns already-loaded results (name -> parsed results/<name>.json) and golden items
    (as returned by golden.schema.load_golden) into the exact text main() writes to
    results/significance.md. No file I/O; the only randomness is the single rng seeded from SEED
    here, consumed in a fixed order, so this function is deterministic for a given input."""
    for g in golden:
        if len(g.passages) != 1:
            raise ValueError(
                f"golden item {g.id} has {len(g.passages)} passages, the pre-registered analysis "
                "assumes exactly one passage per item")

    golden_ids = sorted(g.id for g in golden)
    assert_golden_size(golden_ids)

    for name, result in results.items():
        ids = [item["id"] for item in result["items"]]
        assert_result_coverage(f"{name}.json", ids, golden_ids)
        for item in result["items"]:
            for m in BINARY_METRICS:
                if item[m] not in (0.0, 1.0):
                    raise ValueError(f"{name}.json item {item['id']} has non-binary {m}={item[m]!r}")

    per_item_by_config = {name: per_item(result) for name, result in results.items()}
    no_leakage_ids = sorted(g.id for g in golden if g.leakage and g.leakage.no_leakage)
    assert_no_leakage_size(no_leakage_ids)
    views = {
        f"full (n={len(golden_ids)})": golden_ids,
        f"no-leakage (n={len(no_leakage_ids)})": no_leakage_ids,
    }

    rng = np.random.default_rng(SEED)

    intervals: dict[str, dict] = {}
    for view, ids in views.items():
        intervals[view] = {}
        for name in CONFIG_ORDER:
            intervals[view][name] = {}
            for m in METRICS:
                values = [per_item_by_config[name][i][m] for i in ids]
                intervals[view][name][m] = bootstrap_interval(values, rng, N_RESAMPLES)

    comparisons: dict[str, dict] = {}
    for view, ids in views.items():
        comparisons[view] = {}
        for m in METRICS:
            rows = []
            raw_ps = []
            for first_name, second_name in PAIRS:
                fv = [per_item_by_config[first_name][i][m] for i in ids]
                sv = [per_item_by_config[second_name][i][m] for i in ids]
                if m in BINARY_METRICS:
                    outcome = mcnemar_exact([int(v) for v in fv], [int(v) for v in sv])
                    rows.append({"pair": (first_name, second_name), "b": outcome["b"], "c": outcome["c"],
                                 "p": outcome["p"]})
                    raw_ps.append(outcome["p"])
                else:
                    diff = paired_mean_difference(fv, sv, rng, N_RESAMPLES)
                    p = sign_flip_p(fv, sv, rng, N_PERMUTATIONS)
                    rows.append({"pair": (first_name, second_name), "difference": diff["difference"],
                                 "low": diff["low"], "high": diff["high"], "p": p})
                    raw_ps.append(p)
            adjusted = holm(raw_ps)
            for row, p_holm in zip(rows, adjusted):
                row["p_holm"] = p_holm
            comparisons[view][m] = rows

    return render_significance(intervals, comparisons, seed=SEED, n_resamples=N_RESAMPLES,
                                n_permutations=N_PERMUTATIONS, alpha=ALPHA)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    results = _load_results()
    golden = load_golden(GOLDEN_SET)
    text = build_significance_report(results, golden)
    out_path = RESULTS_DIR / "significance.md"
    out_path.write_text(text, encoding="utf-8")
    print(out_path)


if __name__ == "__main__":
    main()
