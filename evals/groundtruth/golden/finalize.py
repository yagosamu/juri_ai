"""Assemble golden_set.jsonl from triage rows and human labels, and write the calibration report.

Judge-pass items enter only when the blind calibration sample has at most MAX_FALSE_ACCEPTS items the
triage passed and the human rejected. Refuses, rather than guessing, whenever a required human
decision is missing.
Usage: .venv/Scripts/python.exe -m evals.groundtruth.golden.finalize
"""
import json
import sys
from collections import Counter

from evals.groundtruth.config import CALIBRATION_REPORT, CALIBRATION_SAMPLE, GOLDEN_SET, HUMAN_LABELS, TRIAGE
from evals.groundtruth.golden.agreement import cohen_kappa, percent_agreement
from evals.groundtruth.golden.confirm import load_labels
from evals.groundtruth.golden.review import load_candidates
from evals.groundtruth.golden.schema import GoldenItem, Passage, save_golden
from evals.groundtruth.golden.triage import load_triage

MAX_FALSE_ACCEPTS = 0


class FinalizeRefused(RuntimeError):
    pass


def _triage_accepts(row: dict) -> bool:
    return row["status"] == "judged" and not row["flagged"]


def gate(sample_ids: list[str], triage: dict[str, dict], labels: dict[str, dict]) -> dict:
    eligible = [cid for cid in sample_ids if triage[cid]["status"] != "refused"]
    missing = [cid for cid in eligible if cid not in labels or labels[cid]["mode"] != "calibrate"]
    if missing:
        raise FinalizeRefused(f"calibration sample incomplete, {len(missing)} unlabeled, "
                              f"for example {missing[:3]}; run confirm --mode calibrate")
    false_accepts = sorted(c for c in eligible if _triage_accepts(triage[c]) and labels[c]["decision"] != "accept")
    false_rejects = sorted(c for c in eligible if not _triage_accepts(triage[c]) and labels[c]["decision"] == "accept")
    return {"n": len(eligible), "false_accepts": false_accepts, "false_rejects": false_rejects,
            "passed": len(false_accepts) <= MAX_FALSE_ACCEPTS}


def agreement_table(sample_ids: list[str], triage: dict[str, dict], labels: dict[str, dict]) -> list[dict]:
    ids = [cid for cid in sample_ids if triage[cid]["status"] == "judged" and cid in labels]
    if not ids:
        return []
    human, judged = [labels[c] for c in ids], [triage[c]["judge"] for c in ids]
    fields = {
        "answerable": ([h["rubric"]["answerable"] for h in human], [j["answerable"] for j in judged]),
        "leakage": ([h["rubric"]["leakage"] for h in human], [j["leakage"] for j in judged]),
        "category": ([h["category"] for h in human], [j["category"] for j in judged]),
        "also answered by any": ([bool(h["rubric"]["also_answered_by"]) for h in human],
                                 [bool(j["also_answered_by"]) for j in judged]),
        "accept": ([h["decision"] == "accept" for h in human], [_triage_accepts(triage[c]) for c in ids]),
    }
    return [{"field": name, "n": len(ids), "agreement": percent_agreement(h, j), "kappa": cohen_kappa(h, j)}
            for name, (h, j) in fields.items()]


REQUIRED_LABEL_MODE = {"human_blind_calibration": "calibrate", "human_flagged": "flagged",
                       "human_unflagged": "unflagged"}


def assemble(candidates: dict[str, dict], triage: dict[str, dict], labels: dict[str, dict],
             sample_ids: list[str], gate_passed: bool) -> list[GoldenItem]:
    sample = set(sample_ids)
    items, problems = [], []
    for cid in sorted(triage):
        row = triage[cid]
        if row["status"] == "refused":
            continue
        cand, label = candidates[cid], labels.get(cid)
        if cid in sample:
            mode = "human_blind_calibration"
        elif row["flagged"]:
            mode = "human_flagged"
        elif label is not None:
            mode = "human_unflagged"
        elif gate_passed:
            mode = "judge_pass"
        else:
            problems.append(f"{cid}: unflagged and the gate failed, run confirm --mode unflagged")
            continue
        if mode == "judge_pass":
            question, category = cand["question"], cand["category"]
            reviewer, when = f"judge:{row['judge_model']}", row["judged_at"]
            notes = f"judge reasoning: {row['judge']['reasoning']}"
        else:
            if label is None:
                problems.append(f"{cid}: no human decision for {mode}")
                continue
            required = REQUIRED_LABEL_MODE[mode]
            if label.get("mode") != required:
                problems.append(f"{cid}: expected label mode {required!r} for {mode}, found {label.get('mode')!r}")
                continue
            if label["decision"] != "accept":
                continue
            question, category = label["question"], label["category"]
            reviewer, when, notes = label["reviewer"], label["reviewed_at"], ""
        items.append(GoldenItem(id=cid, question=question, category=category,
                                passages=[Passage(doc_id=cand["doc_id"], start=cand["start"], end=cand["end"])],
                                source_article=f"{cand['doc_id']} {cand['header']}", reviewed_by=reviewer,
                                reviewed_at=when, review_mode=mode, notes=notes))
    if problems:
        raise FinalizeRefused(f"{len(problems)} candidates need a decision: " + "; ".join(problems[:5]))
    return items


def _fmt(value: float | None) -> str:
    return "undefined" if value is None else f"{value:.3f}"


def render_report(triage: dict[str, dict], sample_ids: list[str], gate_result: dict, table: list[dict],
                  items: list[GoldenItem], labels: dict[str, dict]) -> str:
    status = Counter(r["status"] for r in triage.values())
    flagged = sum(1 for r in triage.values() if r["status"] != "refused" and r["flagged"])
    reasons = Counter(reason.split(":")[0].split("=")[0] for r in triage.values() for reason in r["flag_reasons"])
    modes = Counter(i.review_mode for i in items)
    rejected = sum(1 for label in labels.values() if label["decision"] != "accept")
    lines = ["# Golden set calibration", "",
             f"Candidates triaged: {len(triage)}. Judged {status['judged']}, judge failed {status['judge_failed']}, "
             f"refused {status['refused']}.",
             f"Flagged by triage: {flagged}.", "", "Flag reasons:", ""]
    lines += [f"- {name}: {count}" for name, count in sorted(reasons.items())]
    lines += ["", "## Blind calibration sample", "", f"Sample size: {gate_result['n']}.", "",
              "| field | n | agreement | Cohen's kappa |", "|---|---|---|---|"]
    lines += [f"| {r['field']} | {r['n']} | {r['agreement']:.3f} | {_fmt(r['kappa'])} |" for r in table]
    lines += ["",
              f"False accepts, triage passed and the human rejected: {len(gate_result['false_accepts'])} {gate_result['false_accepts']}",
              f"False rejects, triage flagged and the human accepted: {len(gate_result['false_rejects'])} {gate_result['false_rejects']}",
              f"Gate, at most {MAX_FALSE_ACCEPTS} false accepts: {'passed' if gate_result['passed'] else 'failed'}.",
              "", "## Golden set", "", "| review mode | items |", "|---|---|"]
    lines += [f"| {mode} | {count} |" for mode, count in sorted(modes.items())]
    lines += ["", f"Rejected by a human: {rejected}.", f"Total golden items: {len(items)}.", "",
              f"With a calibration sample of {gate_result['n']} items, agreement and kappa are coarse estimates."]
    return "\n".join(lines) + "\n"


def main() -> None:
    triage = load_triage(TRIAGE)
    if not triage:
        sys.exit(f"no triage rows in {TRIAGE}; run evals.groundtruth.golden.triage first")
    if not CALIBRATION_SAMPLE.exists():
        sys.exit(f"no calibration sample at {CALIBRATION_SAMPLE}; run evals.groundtruth.golden.confirm "
                 f"--mode calibrate first")
    labels = load_labels(HUMAN_LABELS)
    sample_ids = json.loads(CALIBRATION_SAMPLE.read_text(encoding="utf-8"))["candidate_ids"]
    candidates = {c["candidate_id"]: c for c in load_candidates()}
    try:
        result = gate(sample_ids, triage, labels)
        items = assemble(candidates, triage, labels, sample_ids, result["passed"])
    except FinalizeRefused as exc:
        sys.exit(str(exc))
    save_golden(items, GOLDEN_SET)
    CALIBRATION_REPORT.parent.mkdir(parents=True, exist_ok=True)
    report = render_report(triage, sample_ids, result, agreement_table(sample_ids, triage, labels), items, labels)
    CALIBRATION_REPORT.write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
