# evals/groundtruth/report.py
"""Render results/*.json into results/report.md (overall table, leakage-subset tables, per-category
recall@10, hardest queries).
Usage: .venv/Scripts/python.exe -m evals.groundtruth.report"""
import json
import statistics
import sys

from evals.groundtruth.config import GOLDEN_SET, RESULTS_DIR
from evals.groundtruth.golden.leakage import NGRAM_FLAG
from evals.groundtruth.golden.schema import load_golden
from evals.groundtruth.scorers import METRICS


def load_results() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(RESULTS_DIR.glob("*.json"))]


def render_report(results: list[dict]) -> str:
    if not results:
        raise ValueError(
            "render_report got no results; run "
            "python -m evals.groundtruth.run_retrieval --config production first.")
    lines = ["| config | " + " | ".join(METRICS) + " | p50 search ms |", "|" + "---|" * (len(METRICS) + 2)]
    for r in results:
        o = r["summary"]["overall"]
        p50 = statistics.median(i["latency_ms"] for i in r["items"])
        lines.append(f"| {r['config']['name']} | " + " | ".join(f"{o[m]:.3f}" for m in METRICS) + f" | {p50:.0f} |")
    lines += ["", "p50 search ms: wall-clock time inside retriever.search with the query embedding "
                   "already computed, on the machine that ran it; informational, not gated."]

    subsets = [("summary_no_leakage", f"no-leakage subset (spec): no judge rated leakage heavy and the longest copied run is under {NGRAM_FLAG} tokens"),
               ("summary_short_copy", f"short-copy subset (robustness view): the longest copied run is under {NGRAM_FLAG} tokens; judge leakage labels are ignored")]
    for key, title in subsets:
        lines += ["", title, "", "| config | n | " + " | ".join(METRICS) + " |", "|" + "---|" * (len(METRICS) + 2)]
        for r in results:
            sub = r[key]["overall"]
            values = " | ".join(f"{sub[m]:.3f}" if m in sub else "-" for m in METRICS)
            lines.append(f"| {r['config']['name']} | {sub['n']} | {values} |")

    cats = sorted({c for r in results for c in r["summary"]["by_category"]})
    lines += ["", "recall@10 by category", "", "| config | " + " | ".join(cats) + " |", "|" + "---|" * (len(cats) + 1)]
    for r in results:
        bc = r["summary"]["by_category"]
        lines.append(f"| {r['config']['name']} | " + " | ".join(
            f"{bc[c]['recall@10']:.3f} (n={bc[c]['n']})" if c in bc else "-" for c in cats) + " |")
    questions = {g.id: g.question for g in load_golden(GOLDEN_SET)}
    max_recall10 = max(r["summary"]["overall"]["recall@10"] for r in results)
    tied_names = [r["config"]["name"] for r in results if r["summary"]["overall"]["recall@10"] == max_recall10]
    best = next(r for r in results if r["config"]["name"] == tied_names[0])
    failing = [i for i in best["items"] if i["recall@10"] == 0.0]
    tie_suffix = f", tied with {', '.join(tied_names[1:])}" if len(tied_names) > 1 else ""
    lines += ["", f"queries with recall@10 = 0 under best recall@10 config "
                   f"({best['config']['name']}{tie_suffix}): {len(failing)}", ""]
    lines += [f"- {i['id']} [{i['category']}] {questions.get(i['id'], '')}" for i in failing]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    text = render_report(load_results())
    (RESULTS_DIR / "report.md").write_text(text, encoding="utf-8")
    print(text)
