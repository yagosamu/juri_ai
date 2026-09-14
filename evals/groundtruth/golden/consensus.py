"""Assemble the golden set by consensus of the two rubric v2 judges, decision 13 of the spec.

An item enters only when both judges say the article alone fully answers, no judge names a competitor that
fully answers, the question cites no source, and both verdicts exist. Category is the majority of the generator
and the two judges; with no majority the item is excluded. Leakage never excludes: it is recorded so the
benchmark can report the no-leakage subset. Refuses, rather than guessing, when inputs are incomplete.
Usage: .venv/Scripts/python.exe -m evals.groundtruth.golden.consensus
"""
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from evals.groundtruth.config import CONSENSUS_REPORT, GOLDEN_SET, JUDGMENTS, TRIAGE
from evals.groundtruth.golden.agreement import cohen_kappa, percent_agreement
from evals.groundtruth.golden.judges import ANTHROPIC_JUDGE_MODEL, RUBRIC_VERSION
from evals.groundtruth.golden.jsonl_io import read_jsonl_rows
from evals.groundtruth.golden.leakage import NGRAM_FLAG
from evals.groundtruth.golden.review import load_candidates
from evals.groundtruth.golden.schema import GoldenItem, LeakageSignals, Passage, save_golden
from evals.groundtruth.golden.triage import JUDGE_MODEL as OPENAI_JUDGE_MODEL
from evals.groundtruth.golden.triage import load_triage

JUDGE_MODELS = (OPENAI_JUDGE_MODEL, ANTHROPIC_JUDGE_MODEL)
REVIEWER = "judges:" + "+".join(JUDGE_MODELS)
LIMITATIONS = ("Both judges are language models, one of them a smaller model; each saw truncated competitor "
               "previews, and a competitor the triage did not surface remains possible.")


class ConsensusRefused(RuntimeError):
    pass


@dataclass
class Decision:
    candidate_id: str
    include: bool
    reasons: list[str] = field(default_factory=list)
    category: str | None = None
    leakage: LeakageSignals | None = None


def load_judgments(path: Path) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    if path.exists():
        for row in read_jsonl_rows(path):
            rows.setdefault(row["candidate_id"], row)
    return rows


def majority_category(labels: list[str]) -> str | None:
    value, count = Counter(labels).most_common(1)[0]
    return value if count >= 2 else None


def decide(candidate: dict, triage_row: dict, judgment: dict) -> Decision:
    cid = candidate["candidate_id"]
    verdicts = {model: judgment["judges"].get(model, {}).get("verdict") for model in JUDGE_MODELS}
    reasons = [f"judge_missing:{model}" for model, verdict in verdicts.items() if verdict is None]
    if triage_row["signals"]["cites_source"]:
        reasons.append("cites_source")
    for model, verdict in verdicts.items():
        if verdict is None:
            continue
        if verdict["answerable"] != "yes":
            reasons.append(f"answerable:{model}={verdict['answerable']}")
        if verdict["also_answered_by"]:
            reasons.append(f"also_answered_by:{model}=" + ",".join(verdict["also_answered_by"]))
    category, leakage = None, None
    if all(verdict is not None for verdict in verdicts.values()):
        labels = [candidate["category"]] + [verdicts[model]["category"] for model in JUDGE_MODELS]
        category = majority_category(labels)
        if category is None:
            reasons.append("category_no_majority:" + "/".join(labels))
        judges = {model: verdicts[model]["leakage"] for model in JUDGE_MODELS}
        ngram = triage_row["signals"]["max_shared_ngram"]
        leakage = LeakageSignals(judges=judges, max_shared_ngram=ngram,
                                 no_leakage=all(v != "heavy" for v in judges.values()) and ngram < NGRAM_FLAG)
    return Decision(cid, not reasons, reasons, category, leakage)


def assemble(candidates: list[dict], triage: dict[str, dict],
             judgments: dict[str, dict]) -> tuple[list[GoldenItem], list[Decision]]:
    by_id = {c["candidate_id"]: c for c in candidates}
    problems = []
    for cid, row in sorted(triage.items()):
        if row["status"] == "refused":
            continue
        if cid not in by_id:
            problems.append(f"{cid}: triaged but missing from candidates")
        elif cid not in judgments:
            problems.append(f"{cid}: no judgments row, run evals.groundtruth.golden.judges")
        elif judgments[cid].get("rubric_version") != RUBRIC_VERSION:
            problems.append(f"{cid}: judged under rubric {judgments[cid].get('rubric_version')!r}, "
                            f"expected {RUBRIC_VERSION!r}")
    for cid in sorted(set(by_id) - set(triage)):
        problems.append(f"{cid}: no triage row, run evals.groundtruth.golden.triage")
    if problems:
        raise ConsensusRefused(f"{len(problems)} candidates are not ready: " + "; ".join(problems[:5]))
    items, decisions = [], []
    for cid in sorted(triage):
        if triage[cid]["status"] == "refused":
            decisions.append(Decision(cid, False, ["refused_by_triage"]))
            continue
        cand = by_id[cid]
        decision = decide(cand, triage[cid], judgments[cid])
        decisions.append(decision)
        if decision.include:
            items.append(GoldenItem(
                id=cid, question=cand["question"], category=decision.category,
                passages=[Passage(doc_id=cand["doc_id"], start=cand["start"], end=cand["end"])],
                source_article=f"{cand['doc_id']} {cand['header']}", reviewed_by=REVIEWER,
                reviewed_at=judgments[cid]["judged_at"], review_mode="judge_consensus", leakage=decision.leakage))
    return items, decisions


def agreement_table(judgments: dict[str, dict]) -> list[dict]:
    a_model, b_model = JUDGE_MODELS
    pairs = [(row["judges"][a_model]["verdict"], row["judges"][b_model]["verdict"]) for row in judgments.values()
             if row["judges"].get(a_model, {}).get("verdict") and row["judges"].get(b_model, {}).get("verdict")]
    if not pairs:
        return []
    fields = {
        "answerable": ([a["answerable"] for a, _ in pairs], [b["answerable"] for _, b in pairs]),
        "also answered by any": ([bool(a["also_answered_by"]) for a, _ in pairs],
                                 [bool(b["also_answered_by"]) for _, b in pairs]),
        "leakage": ([a["leakage"] for a, _ in pairs], [b["leakage"] for _, b in pairs]),
        "category": ([a["category"] for a, _ in pairs], [b["category"] for _, b in pairs]),
    }
    return [{"field": name, "n": len(pairs), "agreement": percent_agreement(x, y), "kappa": cohen_kappa(x, y)}
            for name, (x, y) in fields.items()]


def _fmt(value: float | None) -> str:
    return "undefined" if value is None else f"{value:.3f}"


def render_report(decisions: list[Decision], items: list[GoldenItem], table: list[dict]) -> str:
    excluded = [d for d in decisions if not d.include]
    reasons = Counter(key for d in excluded for key in {reason.split(":")[0] for reason in d.reasons})
    by_category = Counter(item.category for item in items)
    no_leakage = sum(1 for item in items if item.leakage and item.leakage.no_leakage)
    lines = ["# Golden set by judge consensus", "",
             f"Judges: {', '.join(JUDGE_MODELS)}. Rubric {RUBRIC_VERSION}. No human legal review.", "",
             f"Candidates: {len(decisions)}. Included: {len(items)}. Excluded: {len(excluded)}.", "",
             "## Exclusion reasons", "", "A candidate can have more than one reason.", "",
             "| reason | candidates |", "|---|---|"]
    lines += [f"| {name} | {count} |" for name, count in sorted(reasons.items())]
    lines += ["", "## Golden set", "", "| category | items |", "|---|---|"]
    lines += [f"| {name} | {count} |" for name, count in sorted(by_category.items())]
    lines += ["", f"No-leakage subset: {no_leakage} of {len(items)} items, where no judge rated leakage heavy and "
                  f"the longest copied run is under {NGRAM_FLAG} tokens.",
              "", "## Agreement between judges", "", "| field | n | agreement | Cohen's kappa |", "|---|---|---|---|"]
    lines += [f"| {row['field']} | {row['n']} | {row['agreement']:.3f} | {_fmt(row['kappa'])} |" for row in table]
    lines += ["", LIMITATIONS]
    return "\n".join(lines) + "\n"


def main() -> None:
    triage = load_triage(TRIAGE)
    if not triage:
        sys.exit(f"no triage rows in {TRIAGE}; run evals.groundtruth.golden.triage first")
    judgments = load_judgments(JUDGMENTS)
    try:
        items, decisions = assemble(load_candidates(), triage, judgments)
    except ConsensusRefused as exc:
        sys.exit(str(exc))
    save_golden(items, GOLDEN_SET)
    CONSENSUS_REPORT.parent.mkdir(parents=True, exist_ok=True)
    report = render_report(decisions, items, agreement_table(judgments))
    CONSENSUS_REPORT.write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
